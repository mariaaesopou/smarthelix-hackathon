"""Run one ETL from the command line.

    python -m pipeline.etl --source source_a --mode full
    python -m pipeline.etl --source source_a --mode incremental

DATABASE_URL and MOCK_SOURCES_URL default to the local compose stack.
Exit codes follow packages/shared/constants.json: 0 success, 75 retry later,
65 permanent failure. The output holds counts and the run id only (rule 29).
"""

import argparse
import json
import os
import sys

import psycopg

from pipeline.connectors.http import SourceUnavailable
from pipeline.connectors.source_a import SourceAConnector
from pipeline.constants import EXIT_PERMANENT, EXIT_RETRYABLE, EXIT_SUCCESS
from pipeline.etl.run import RunAlreadyActive, run_etl

CONNECTORS = {
    "source_a": lambda base_url: SourceAConnector(base_url),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline.etl", description=__doc__.split("\n")[0])
    parser.add_argument("--source", required=True, choices=sorted(CONNECTORS))
    parser.add_argument("--mode", choices=["full", "incremental"], default="incremental")
    parser.add_argument("--no-resolve", action="store_true", help="load source_records only")
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL", "postgres://smarthelix:smarthelix_dev@127.0.0.1:5432/smarthelix")
    base_url = os.environ.get("MOCK_SOURCES_URL", "http://localhost:4000")
    secret = os.environ.get("ERASURE_HMAC_SECRET", "").encode("utf-8") or None
    if secret is None:
        print("warning: ERASURE_HMAC_SECRET is not set, so the erasure blocklist is not checked",
              file=sys.stderr)

    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            result = run_etl(conn, CONNECTORS[args.source](base_url), args.mode,
                             erasure_secret=secret, resolve_after=not args.no_resolve)
    except (RunAlreadyActive, SourceUnavailable, psycopg.OperationalError) as err:
        print(json.dumps({"status": "retry", "error": type(err).__name__}), file=sys.stderr)
        return EXIT_RETRYABLE
    except Exception as err:  # a bug or bad data: retrying will not help
        print(json.dumps({"status": "failed", "error": type(err).__name__}), file=sys.stderr)
        return EXIT_PERMANENT

    print(json.dumps({"status": "ok", "run_id": result.run_id, "counts": result.counts,
                      "invalid_reasons": result.errors}, ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
