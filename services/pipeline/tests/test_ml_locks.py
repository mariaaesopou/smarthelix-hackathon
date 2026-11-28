"""Advisory locks, dead-run cleanup and old-run pruning, against the Compose Postgres."""

import os
import uuid

import psycopg
import pytest

from pipeline.cli import main
from pipeline.constants import K_ERASURE, K_ML
from pipeline.errors import RetryableError
from pipeline.spark_jobs.ml_run import acquire_run_locks, prune_old_runs, release_run_locks

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture
def conns():
    made = []

    def make():
        c = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
        made.append(c)
        return c

    runs = make().execute("SELECT id FROM ml_runs").fetchall()
    batches = make().execute("SELECT id FROM ml_batches").fetchall()
    pointer = make().execute("SELECT run_id FROM ml_current WHERE kind = 'clustering'").fetchone()
    yield make
    c = make()
    if pointer:  # the pointer must move off a test run before that run can be deleted
        c.execute("UPDATE ml_current SET run_id = %s WHERE kind = 'clustering'", (pointer[0],))
    else:
        c.execute("DELETE FROM ml_current WHERE kind = 'clustering'")
    c.execute("DELETE FROM ml_runs WHERE id <> ALL(%s)", ([r[0] for r in runs],))
    c.execute("DELETE FROM ml_batches WHERE id <> ALL(%s)", ([b[0] for b in batches],))
    for x in made:
        x.close()


def count_runs(c):
    return c.execute("SELECT count(*) FROM ml_runs").fetchone()[0]


def test_a_held_ml_lock_makes_the_job_exit_75_without_creating_a_run(conns):
    holder, probe = conns(), conns()
    holder.execute("SELECT pg_advisory_lock(%s)", (K_ML,))
    before = count_runs(probe)
    assert main(["similarity"]) == 75
    assert count_runs(probe) == before
    holder.execute("SELECT pg_advisory_unlock(%s)", (K_ML,))


def test_a_running_erasure_makes_the_job_exit_75(conns):
    holder, probe = conns(), conns()
    holder.execute("SELECT pg_advisory_lock(%s)", (K_ERASURE,))  # exclusive, like the erasure script
    before = count_runs(probe)
    assert main(["similarity"]) == 75
    assert count_runs(probe) == before
    holder.execute("SELECT pg_advisory_unlock(%s)", (K_ERASURE,))


def test_two_runs_cannot_hold_the_ml_lock_but_release_frees_it(conns):
    a, b = conns(), conns()
    acquire_run_locks(a)
    with pytest.raises(RetryableError):
        acquire_run_locks(b)
    # the failed attempt must not leave its shared K_ERASURE lock behind
    held = b.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()").fetchone()[0]
    assert held == 0
    release_run_locks(a)
    acquire_run_locks(b)


def test_a_run_left_running_by_a_dead_process_is_closed(conns):
    c = conns()
    batch = c.execute("INSERT INTO ml_batches (data_version, status) VALUES (1, 'running') RETURNING id").fetchone()[0]
    run = c.execute("INSERT INTO ml_runs (batch_id, kind, data_version, params) VALUES (%s, 'clustering', 1, '{}') RETURNING id",
                    (batch,)).fetchone()[0]
    worker = conns()
    assert acquire_run_locks(worker) == 1
    assert c.execute("SELECT status FROM ml_runs WHERE id = %s", (run,)).fetchone()[0] == "failed"
    assert c.execute("SELECT status FROM ml_batches WHERE id = %s", (batch,)).fetchone()[0] == "failed"
    release_run_locks(worker)


def test_prune_keeps_current_and_one_previous_and_never_touches_running(conns):
    c = conns()
    # force_rollback: the dev database's own seed runs are candidates for pruning too, so leave them be.
    with c.transaction(force_rollback=True):
        batch = c.execute("INSERT INTO ml_batches (data_version, status) VALUES (1, 'succeeded') RETURNING id").fetchone()[0]
        ids = []
        for hours_ago in (5, 4, 3, 2, 1):
            ids.append(c.execute(
                "INSERT INTO ml_runs (batch_id, kind, data_version, params, status, finished_at) "
                "VALUES (%s, 'clustering', 1, '{}', 'succeeded', now() - make_interval(hours => %s)) RETURNING id",
                (batch, hours_ago)).fetchone()[0])
        failed = c.execute("INSERT INTO ml_runs (batch_id, kind, data_version, params, status, finished_at) "
                           "VALUES (%s, 'clustering', 1, '{}', 'failed', now()) RETURNING id", (batch,)).fetchone()[0]
        running_batch = c.execute("INSERT INTO ml_batches (data_version, status) VALUES (2, 'running') RETURNING id").fetchone()[0]
        running = c.execute("INSERT INTO ml_runs (batch_id, kind, data_version, params) "
                            "VALUES (%s, 'clustering', 2, '{}') RETURNING id", (running_batch,)).fetchone()[0]
        c.execute("INSERT INTO ml_current (kind, run_id) VALUES ('clustering', %s) "
                  "ON CONFLICT (kind) DO UPDATE SET run_id = EXCLUDED.run_id", (ids[-1],))

        assert prune_old_runs(c, "clustering") >= 4  # 3 oldest succeeded + the failed one (+ any seed run)
        left = {r[0] for r in c.execute("SELECT id FROM ml_runs WHERE kind = 'clustering'")}
        assert left == {ids[-1], ids[-2], running}
        assert failed not in left
