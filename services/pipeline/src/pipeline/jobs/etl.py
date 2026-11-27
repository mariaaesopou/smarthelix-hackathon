"""`python -m pipeline etl --source source_a --mode full|incremental`: one connector run.

Prints the run id and counts as JSON on stdout (internal ids and counts only,
rule 29). Exit codes come from the CLI: a source that is down or another run of
the same source is retryable (75); anything unexpected also retries, and
BullMQ's attempt cap stops a real bug from looping.
"""

import argparse
import json
import os
import sys

from ..connectors.http import SourceUnavailable
from ..connectors.source_a import SourceAConnector
from ..db import connect
from ..errors import RetryableError
from ..etl.run import RunAlreadyActive, run_etl

CONNECTORS = {
    "source_a": SourceAConnector,
}


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--source", required=True, choices=sorted(CONNECTORS))
    p.add_argument("--mode", choices=["full", "incremental"], default="incremental",
                   help="incremental asks only for records changed since the last successful run")
    p.add_argument("--no-resolve", action="store_true", help="load source_records only")


def run(args: argparse.Namespace) -> None:
    base_url = os.environ.get("MOCK_SOURCES_URL", "http://localhost:4000")
    secret = os.environ.get("ERASURE_HMAC_SECRET", "").encode("utf-8") or None
    if secret is None:
        print("warning: ERASURE_HMAC_SECRET is not set, so the erasure blocklist is not checked",
              file=sys.stderr)

    conn = connect()
    try:
        result = run_etl(conn, CONNECTORS[args.source](base_url), args.mode,
                         erasure_secret=secret, resolve_after=not args.no_resolve)
    except RunAlreadyActive as exc:
        raise RetryableError(f"another {args.source} run is queued or running") from exc
    except SourceUnavailable as exc:
        raise RetryableError(str(exc)) from exc
    finally:
        conn.close()

    print(json.dumps({"run_id": result.run_id, "counts": result.counts,
                      "invalid_reasons": result.errors}, ensure_ascii=False), flush=True)
