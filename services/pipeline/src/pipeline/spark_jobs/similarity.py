"""`python -m pipeline similarity`: profiles -> compute_similar -> similar_profiles.

    1. start a run (ml_runs row) and note data_version
    2. read live profiles over JDBC, call Role 2's compute_similar
    3. write the rows under the run's id (JDBC append)
    4. validate what landed, then switch ml_current in one transaction

Spark and Role 2's package are imported inside run(), so importing this module (and
the CLI) stays cheap and `selftest` never loads Spark.
"""

import argparse
import os
import sys
import time
import uuid

from ..db import connect, database_url
from ..errors import PermanentError
from .ml_run import (Run, acquire_run_locks, fail_run, finish_run, prune_old_runs,
                     release_run_locks, start_run)

KIND = "similarity"
TABLE = "similar_profiles"


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--batch-id", type=uuid.UUID, default=None,
                   help="ml_batches id to attach to; omit to create (and close) a batch for this run")
    p.add_argument("--k", type=int, default=20, help="neighbours stored per profile")


def _write(df, table: str) -> None:
    from smarthelix_ml.db import jdbc_options

    o = jdbc_options(database_url())
    # stringtype=unspecified: Spark sends uuid ids as varchar, which Postgres refuses for uuid
    # columns; unspecified lets Postgres cast them. rewriteBatchedInserts speeds bulk inserts.
    url = o["url"] + "?stringtype=unspecified&rewriteBatchedInserts=true"
    df.write.jdbc(url, table, mode="append",
                  properties={"user": o["user"], "password": o["password"],
                              "driver": o["driver"], "batchsize": "5000"})


def _validate(conn, run: Run, k: int) -> dict:
    rows, profiles, deepest = conn.execute(
        "SELECT count(*), count(DISTINCT profile_id), coalesce(max(rank), 0) FROM similar_profiles WHERE run_id = %s",
        (run.id,),
    ).fetchone()
    if rows == 0:
        raise PermanentError("compute_similar produced no rows")
    if deepest > k:
        raise PermanentError(f"rank {deepest} exceeds k={k}")
    return {"rows": rows, "profiles_with_list": profiles, "k": k}


def run(args: argparse.Namespace, compute=None) -> None:
    from pyspark.sql import functions as F
    from smarthelix_ml.db import load_profiles_jdbc
    from smarthelix_ml.session import get_spark
    from smarthelix_ml.similarity import compute_similar

    compute = compute or compute_similar
    conn = connect()
    try:
        reaped = acquire_run_locks(conn, args.batch_id)
        if reaped:
            print(f"closed {reaped} run(s) left running by a dead process", file=sys.stderr, flush=True)
        current = start_run(conn, KIND, args.batch_id, {"k": args.k})
    except BaseException:
        conn.close()  # also releases any lock taken
        raise
    started = time.perf_counter()
    try:
        spark = get_spark(app_name=KIND, driver_memory=os.environ.get("SPARK_DRIVER_MEMORY", "2g"), jdbc=True)
        try:
            profiles = load_profiles_jdbc(spark, database_url())
            result = compute(profiles, args.k).withColumn("run_id", F.lit(str(current.id)))
            _write(result, TABLE)
        finally:
            spark.stop()
        metrics = _validate(conn, current, args.k)
        metrics["seconds"] = round(time.perf_counter() - started, 1)
        finish_run(conn, current, metrics)
        metrics["pruned_runs"] = prune_old_runs(conn, KIND)
        print(f"similarity run {current.id} ok: {metrics}", flush=True)
    except ValueError as exc:
        # e.g. "empty vocabulary": too little text in the data. Retrying cannot add text.
        fail_run(conn, current, TABLE, str(exc))
        raise PermanentError(str(exc)) from exc
    except Exception as exc:
        fail_run(conn, current, TABLE, str(exc))
        raise  # PermanentError / RetryableError keep their meaning; anything else exits 75
    finally:
        release_run_locks(conn)
        conn.close()
