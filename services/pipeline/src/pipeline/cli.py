"""Entry point the Node worker spawns: `python -m pipeline <job> [options]`.

Contract with the launcher:
  * options arrive as CLI arguments (small: ids and flags, never data);
  * logs go to stderr, so stdout stays free for machine-readable results later;
  * the exit code is the verdict: 0 ok, 75 retryable, 65 permanent.
"""

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence

from .errors import EXIT_OK, EXIT_PERMANENT, EXIT_RETRYABLE, PermanentError, RetryableError
from .jobs import selftest
from .spark_jobs import similarity

# Job name -> function that configures its subparser and a function that runs it.
JOBS: dict[str, tuple[Callable[[argparse.ArgumentParser], None], Callable[[argparse.Namespace], None]]] = {
    "selftest": (selftest.add_arguments, selftest.run),
    "similarity": (similarity.add_arguments, similarity.run),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="job", required=True)
    for name, (add_arguments, _run) in JOBS.items():
        add_arguments(sub.add_parser(name))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        # argparse exits 2 on bad arguments; a bad command line never fixes itself.
        return EXIT_OK if exc.code in (0, None) else EXIT_PERMANENT

    try:
        JOBS[args.job][1](args)
    except PermanentError as exc:
        print(f"permanent failure: {exc}", file=sys.stderr)
        return EXIT_PERMANENT
    except RetryableError as exc:
        print(f"retryable failure: {exc}", file=sys.stderr)
        return EXIT_RETRYABLE
    except Exception:  # noqa: BLE001 - deliberate catch-all, see below
        # Decision: unexpected errors fail open (retry). Spark/JDBC failures reach us
        # as opaque py4j exceptions and are mostly transient (DB blip, OOM, timeout).
        # BullMQ's attempt cap stops a real bug from looping forever.
        traceback.print_exc()
        return EXIT_RETRYABLE
    return EXIT_OK
