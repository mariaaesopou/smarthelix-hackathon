"""The life of one ML run (docs/architecture.md, item 17).

    start_run   insert an ml_runs row (status 'running') and snapshot data_version
    ... the job writes its rows under that run_id ...
    finish_run  ONE transaction: mark it succeeded and point ml_current at it
    fail_run    mark it failed and delete its partial rows; ml_current is untouched

Around a run: acquire_run_locks / release_run_locks (K_ERASURE shared, then K_ML exclusive,
on the job's own connection for its whole life) and prune_old_runs after the pointer moves.

Readers only ever follow ml_current, so they see the old complete results until the
new run is complete and validated, never a half-written mix.
"""

import uuid
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from ..constants import K_ERASURE, K_ML
from ..errors import PermanentError, RetryableError

# Tables holding a run's result rows (all cascade from ml_runs, but a dead run is deleted by
# marking it failed, so its partial rows are removed explicitly).
RESULT_TABLES = ("similar_profiles", "potential_partners", "cluster_assignments")


@dataclass(frozen=True)
class Run:
    id: uuid.UUID
    batch_id: uuid.UUID
    kind: str
    data_version: int
    owns_batch: bool  # True when no batch was supplied, so this run created (and closes) its own


def start_run(conn: psycopg.Connection, kind: str, batch_id: uuid.UUID | None, params: dict) -> Run:
    owns_batch = batch_id is None
    try:
        with conn.transaction():
            # Snapshot BEFORE reading profiles: if data changes during the run, this run is
            # stamped with the older version, so the sweep sees it as stale and re-runs. Safe side.
            data_version = conn.execute("SELECT data_version FROM pipeline_state").fetchone()[0]
            if owns_batch:
                batch_id = conn.execute(
                    "INSERT INTO ml_batches (data_version, status) VALUES (%s, 'running') RETURNING id",
                    (data_version,),
                ).fetchone()[0]
            run_id = conn.execute(
                "INSERT INTO ml_runs (batch_id, kind, data_version, params) VALUES (%s, %s, %s, %s) RETURNING id",
                (batch_id, kind, data_version, Jsonb(params)),
            ).fetchone()[0]
    except psycopg.errors.UniqueViolation as exc:
        # ml_batches_one_active: a queued or running batch already exists.
        raise RetryableError("another ML batch is already queued or running") from exc
    except psycopg.errors.ForeignKeyViolation as exc:
        raise PermanentError(f"batch {batch_id} does not exist") from exc
    return Run(run_id, batch_id, kind, data_version, owns_batch)


def finish_run(conn: psycopg.Connection, run: Run, metrics: dict) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE ml_runs SET status = 'succeeded', finished_at = now(), metrics = %s WHERE id = %s",
            (Jsonb(metrics), run.id),
        )
        conn.execute(
            "INSERT INTO ml_current (kind, run_id) VALUES (%s, %s) "
            "ON CONFLICT (kind) DO UPDATE SET run_id = EXCLUDED.run_id",
            (run.kind, run.id),
        )
        if run.owns_batch:
            conn.execute("UPDATE ml_batches SET status = 'succeeded', finished_at = now() WHERE id = %s", (run.batch_id,))


def fail_run(conn: psycopg.Connection, run: Run, table: str, error: str) -> None:
    """Best effort: a failure while cleaning up must never hide the original error."""
    try:
        conn.rollback()  # drop whatever transaction the failure left open
        with conn.transaction():
            conn.execute(sql.SQL("DELETE FROM {} WHERE run_id = %s").format(sql.Identifier(table)), (run.id,))
            conn.execute(
                "UPDATE ml_runs SET status = 'failed', finished_at = now(), metrics = %s WHERE id = %s",
                (Jsonb({"error": error[:500]}), run.id),
            )
            if run.owns_batch:
                conn.execute("UPDATE ml_batches SET status = 'failed', finished_at = now() WHERE id = %s", (run.batch_id,))
    except Exception:  # noqa: BLE001
        pass


def acquire_run_locks(conn: psycopg.Connection, keep_batch: uuid.UUID | None = None) -> int:
    """Take K_ERASURE (shared) then K_ML (exclusive) for the life of `conn`; always in this order.

    Session-level locks: they vanish when the connection dies, so a killed job never holds
    them. Never blocks. A held lock means "try again later" (exit 75), not a failure.
    Returns how many dead runs were cleaned up (see _reap_dead_runs).
    """
    if not conn.execute("SELECT pg_try_advisory_lock_shared(%s)", (K_ERASURE,)).fetchone()[0]:
        raise RetryableError("an erasure is running")
    if not conn.execute("SELECT pg_try_advisory_lock(%s)", (K_ML,)).fetchone()[0]:
        conn.execute("SELECT pg_advisory_unlock_shared(%s)", (K_ERASURE,))
        raise RetryableError("another ML run holds the ML lock")
    return _reap_dead_runs(conn, keep_batch)


def release_run_locks(conn: psycopg.Connection) -> None:
    """Best effort; closing the connection releases them anyway."""
    try:
        conn.execute("SELECT pg_advisory_unlock(%s)", (K_ML,))
        conn.execute("SELECT pg_advisory_unlock_shared(%s)", (K_ERASURE,))
    except Exception:  # noqa: BLE001
        pass


def _reap_dead_runs(conn: psycopg.Connection, keep_batch: uuid.UUID | None) -> int:
    """Close runs left 'running' by a process that died (OOM kill, worker restart).

    Only safe while holding K_ML exclusively: no other ML job is alive, so a run still
    marked running cannot be in progress. Without this, one killed run blocks every later
    run through the one-active-batch index.
    """
    with conn.transaction():
        dead = [r[0] for r in conn.execute("SELECT id FROM ml_runs WHERE status = 'running'")]
        for table in RESULT_TABLES:
            conn.execute(sql.SQL("DELETE FROM {} WHERE run_id = ANY(%s)").format(sql.Identifier(table)), (dead,))
        conn.execute(
            "UPDATE ml_runs SET status = 'failed', finished_at = now(), "
            "metrics = coalesce(metrics, '{}'::jsonb) || %s WHERE id = ANY(%s)",
            (Jsonb({"error": "process died before finishing; closed by the next run"}), dead),
        )
        conn.execute(
            "UPDATE ml_batches SET status = 'failed', finished_at = now() "
            "WHERE status = 'running' AND (%s::uuid IS NULL OR id <> %s::uuid)",
            (keep_batch, keep_batch),
        )
    return len(dead)


def prune_old_runs(conn: psycopg.Connection, kind: str) -> int:
    """Keep the current run and the one before it (a fast rollback target); delete the rest.

    Each similarity run is about 40k rows, so they pile up. Running runs are never touched.
    Best effort: failing to prune must not fail a run that already succeeded.
    """
    try:
        with conn.transaction():
            cur = conn.execute(
                "DELETE FROM ml_runs WHERE kind = %(k)s AND status IN ('succeeded', 'failed') "
                "AND id NOT IN (SELECT run_id FROM ml_current WHERE kind = %(k)s) "
                "AND id NOT IN (SELECT id FROM ml_runs WHERE kind = %(k)s AND status = 'succeeded' "
                "               AND id NOT IN (SELECT run_id FROM ml_current WHERE kind = %(k)s) "
                "               ORDER BY finished_at DESC NULLS LAST LIMIT 1)",
                {"k": kind},
            )
            return cur.rowcount
    except Exception:  # noqa: BLE001
        return 0
