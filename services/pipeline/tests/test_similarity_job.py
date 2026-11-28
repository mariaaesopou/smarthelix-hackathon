"""The similarity runner against a real database (the Compose Postgres with the 2k seed).

These check the DATABASE, not the job's own output: an earlier version printed "ok" while its
final transaction had been rolled back. They skip only when DATABASE_URL is not set at all
(running outside the worker container); with it set but unreachable they FAIL, on purpose.
"""

import argparse
import os
import uuid
from types import SimpleNamespace

import psycopg
import pytest

from pipeline.cli import main
from pipeline.errors import PermanentError
from pipeline.spark_jobs import similarity

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set: run inside the worker container"
)


@pytest.fixture
def db():
    """A connection plus a snapshot, so each test leaves the dev database as it found it."""
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    runs = [r[0] for r in conn.execute("SELECT id FROM ml_runs")]
    batches = [r[0] for r in conn.execute("SELECT id FROM ml_batches")]
    pointer = conn.execute("SELECT run_id FROM ml_current WHERE kind = 'similarity'").fetchone()
    live = conn.execute("SELECT count(*) FROM profiles WHERE deleted_at IS NULL AND merged_into IS NULL").fetchone()[0]
    assert live >= 100, "load the seed first: pnpm db:seed (db/seeds/002_profiles.sql)"
    yield SimpleNamespace(conn=conn, runs=runs, live=live)
    # Restore the pointer BEFORE deleting runs (ml_current references ml_runs), then remove
    # what the test created; similar_profiles rows go with their run (ON DELETE CASCADE).
    if pointer:
        conn.execute("UPDATE ml_current SET run_id = %s WHERE kind = 'similarity'", (pointer[0],))
    else:
        conn.execute("DELETE FROM ml_current WHERE kind = 'similarity'")
    conn.execute("DELETE FROM ml_runs WHERE id <> ALL(%s)", (runs,))
    conn.execute("DELETE FROM ml_batches WHERE id <> ALL(%s)", (batches,))
    conn.close()


def new_run(db):
    rows = db.conn.execute(
        "SELECT id, status, batch_id, metrics FROM ml_runs WHERE kind = 'similarity' AND id <> ALL(%s)",
        (db.runs,),
    ).fetchall()
    assert len(rows) == 1, f"expected exactly one new run, found {len(rows)}"
    return rows[0]


def test_a_successful_run_is_committed_and_becomes_current(db):
    assert main(["similarity", "--k", "5"]) == 0

    run_id, status, batch_id, metrics = new_run(db)
    assert status == "succeeded"
    pointer = db.conn.execute("SELECT run_id FROM ml_current WHERE kind = 'similarity'").fetchone()[0]
    assert pointer == run_id, "ml_current must point at the new run"

    rows, profiles, deepest = db.conn.execute(
        "SELECT count(*), count(DISTINCT profile_id), max(rank) FROM similar_profiles WHERE run_id = %s", (run_id,)
    ).fetchone()
    assert rows > 0 and 0 < profiles <= db.live and deepest <= 5
    assert metrics["rows"] == rows
    batch = db.conn.execute("SELECT status FROM ml_batches WHERE id = %s", (batch_id,)).fetchone()[0]
    assert batch == "succeeded"


def test_a_failing_run_is_marked_failed_and_leaves_the_old_results_alone(db):
    before = db.conn.execute("SELECT run_id FROM ml_current WHERE kind = 'similarity'").fetchone()

    def boom(profiles, k):
        raise ValueError("empty vocabulary")

    with pytest.raises(PermanentError, match="empty vocabulary"):
        similarity.run(argparse.Namespace(batch_id=None, k=5), compute=boom)

    run_id, status, batch_id, _ = new_run(db)
    assert status == "failed"
    assert db.conn.execute("SELECT count(*) FROM similar_profiles WHERE run_id = %s", (run_id,)).fetchone()[0] == 0
    assert db.conn.execute("SELECT run_id FROM ml_current WHERE kind = 'similarity'").fetchone() == before
    assert db.conn.execute("SELECT status FROM ml_batches WHERE id = %s", (batch_id,)).fetchone()[0] == "failed"


def test_an_active_batch_makes_the_run_retryable(db):
    # 'queued' (created by the sweep, waiting its turn). A batch left 'running' by a dead process is
    # closed by the next run instead (test_ml_locks.py), so it no longer blocks.
    db.conn.execute("INSERT INTO ml_batches (data_version, status) VALUES (0, 'queued')")
    assert main(["similarity"]) == 75  # RetryableError: try again once that batch is done
    assert db.conn.execute("SELECT count(*) FROM ml_runs WHERE id <> ALL(%s)", (db.runs,)).fetchone()[0] == 0


def test_an_unknown_batch_id_is_permanent(db):
    assert main(["similarity", "--batch-id", str(uuid.uuid4())]) == 65


def test_a_malformed_batch_id_is_permanent(db):
    assert main(["similarity", "--batch-id", "not-a-uuid"]) == 65
