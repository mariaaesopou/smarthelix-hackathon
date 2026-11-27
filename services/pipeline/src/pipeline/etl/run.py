"""One ETL run of one source: extract page by page, transform, load, then resolve."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from psycopg import Connection
from psycopg.types.json import Jsonb

from pipeline.connectors.base import Connector
from pipeline.constants import K_ERASURE
from pipeline.etl.load import upsert
from pipeline.resolution.one_to_one import resolve

Mode = Literal["full", "incremental"]

# An incremental run asks for a little more than the last watermark (rule 1);
# the upsert makes the overlap harmless.
OVERLAP = timedelta(minutes=5)


class RunAlreadyActive(Exception):
    """Another queued or running ETL exists for this source (retry later)."""


@dataclass
class RunResult:
    run_id: str
    counts: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)


def last_watermark(conn: Connection, source: str) -> datetime | None:
    row = conn.execute(
        "SELECT watermark FROM sync_runs WHERE source = %s AND status IN ('etl_done', 'resolved')"
        " AND watermark IS NOT NULL ORDER BY created_at DESC LIMIT 1", (source,)).fetchone()
    return row[0] if row else None


def start_run(conn: Connection, source: str, mode: Mode) -> str:
    from psycopg.errors import UniqueViolation
    try:
        with conn.transaction():
            (run_id,) = conn.execute(
                "INSERT INTO sync_runs (source, mode, status, started_at)"
                " VALUES (%s, %s, 'etl_running', now()) RETURNING id::text", (source, mode)).fetchone()
    except UniqueViolation as err:  # index sync_runs_one_active
        raise RunAlreadyActive(source) from err
    return run_id


def run_etl(conn: Connection, connector: Connector, mode: Mode,
            erasure_secret: bytes | None = None, resolve_after: bool = True) -> RunResult:
    """Run extract-transform-load for one source and record it in sync_runs.

    Each page and the run's cursor are committed together (rule 1), so a failed
    run never leaves half a page. The watermark only moves when the whole run
    succeeds; on failure the run is marked failed and the error re-raised.
    """
    source = connector.source
    since = None
    if mode == "incremental" and (mark := last_watermark(conn, source)):
        since = mark - OVERLAP
    result = RunResult(run_id=start_run(conn, source, mode))
    newest: datetime | None = None

    try:
        for page in connector.pages(since):
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock_shared(%s)", (K_ERASURE,))
                for raw in page.records:
                    result.counts["fetched"] += 1
                    mapped = connector.map(raw)
                    if mapped.record is None:
                        result.counts["invalid"] += 1
                        result.errors[mapped.error or "invalid"] += 1
                        continue
                    result.counts[upsert(conn, mapped.record, result.run_id, erasure_secret)] += 1
                    stamp = mapped.record.source_updated_at
                    if stamp and (newest is None or stamp > newest):
                        newest = stamp
                conn.execute("UPDATE sync_runs SET cursor = %s, counts = %s WHERE id = %s",
                             (page.next_cursor, Jsonb(dict(result.counts)), result.run_id))

        with conn.transaction():
            conn.execute(
                "UPDATE sync_runs SET status = 'etl_done', cursor = NULL, counts = %s,"
                " watermark = coalesce(%s, watermark, %s) WHERE id = %s",
                (Jsonb(dict(result.counts)), newest, since, result.run_id))
        if resolve_after:
            resolved = resolve(conn)
            result.counts["profiles_created"] = resolved.created
            result.counts["profiles_updated"] = resolved.updated
            with conn.transaction():
                conn.execute(
                    "UPDATE sync_runs SET status = 'resolved', counts = %s, finished_at = now()"
                    " WHERE id = %s", (Jsonb(dict(result.counts)), result.run_id))
    except BaseException as err:
        with conn.transaction():
            conn.execute(
                "UPDATE sync_runs SET status = 'failed', error_code = %s, counts = %s,"
                " finished_at = now() WHERE id = %s",
                (type(err).__name__, Jsonb(dict(result.counts)), result.run_id))
        raise
    return result
