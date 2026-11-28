"""A job that does no real work: it fakes an outcome so the plumbing can be tested.

Used by unit tests and by the Node launcher's tests (exit codes, timeouts, kills)
without needing Spark or a database.
"""

import argparse
import time

from ..errors import PermanentError, RetryableError


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--outcome", choices=["ok", "retry", "permanent", "crash"], default="ok")
    p.add_argument("--retry-after", type=float, default=None, help="seconds hint for --outcome retry")
    p.add_argument("--sleep", type=float, default=0.0, help="seconds to wait first (timeout tests)")
    p.add_argument("--spark", action="store_true", help="also start a local Spark session")


def run(args: argparse.Namespace) -> None:
    if args.spark:
        from smarthelix_ml.session import get_spark  # imported lazily: Spark is slow to load

        spark = get_spark(app_name="selftest")
        try:
            print(f"spark ok: {spark.range(5).count()} rows", flush=True)
        finally:
            spark.stop()
    time.sleep(args.sleep)
    if args.outcome == "retry":
        raise RetryableError("selftest asked for a retryable failure", retry_after_s=args.retry_after)
    if args.outcome == "permanent":
        raise PermanentError("selftest asked for a permanent failure")
    if args.outcome == "crash":
        raise RuntimeError("selftest simulated an unexpected bug")
