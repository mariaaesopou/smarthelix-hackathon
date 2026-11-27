"""The life of one ML run (docs/architecture.md, item 17).

    start_run   insert an ml_runs row (status 'running') and snapshot data_version
    ... the job writes its rows under that run_id ...
    finish_run  ONE transaction: mark it succeeded and point ml_current at it
    fail_run    mark it failed and delete its partial rows; ml_current is untouched

Readers only ever follow ml_current, so they see the old complete results until the
new run is complete and validated, never a half-written mix.
"""

import uuid
from dataclasses import dataclass

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from ..errors import PermanentError, RetryableError


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
