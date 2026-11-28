"""ETL against the local compose database, inside a transaction that is rolled back.

Fails when the database is unreachable; SKIP_DB_TESTS=1 skips on purpose.
"""

import os
from datetime import datetime, timezone

import psycopg
import pytest

from pipeline.connectors.base import Mapped, Page
from pipeline.connectors.source_a import to_normalized
from pipeline.etl.load import erasure_key
from pipeline.etl.run import OVERLAP, run_etl

URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
    "DATABASE_URL", "postgres://smarthelix:smarthelix_dev@127.0.0.1:5432/smarthelix")
SOURCE = "zz_test"


def raw(n: int, **change) -> dict:
    return {
        "id": f"t-{n}", "company_name": f"Zzqetl Company {n}", "category": "SME",
        "summary": "Παραδοσιακά γλυκά", "industry": "food", "location": "Κρήτη",
        "capabilities": ["pastry"], "products": ["cakes"], "looking_for": ["web development"],
        "languages": ["el"], "website": None,
        "profile_url": f"https://example.org/zz/t-{n}",
        "last_modified": f"2026-11-{10 + n:02d}T10:00:00Z",
    } | change


class FakeConnector:
    """Serves a fixed list of source A records under the test source name."""

    source = SOURCE

    def __init__(self, records, per_page=2):
        self.records, self.per_page, self.since_seen = records, per_page, []

    def pages(self, since, cursor=None):
        self.since_seen.append(since)
        rows = [r for r in self.records
                if since is None or datetime.fromisoformat(r["last_modified"]) >= since]
        for i in range(0, len(rows), self.per_page):
            nxt = i + self.per_page
            yield Page(records=rows[i:nxt], next_cursor=str(nxt) if nxt < len(rows) else None)

    def map(self, raw):
        try:
            return Mapped(record=to_normalized(raw).model_copy(update={"source": SOURCE}))
        except Exception:
            return Mapped(error="invalid")


@pytest.fixture
def conn():
    # An unreachable database FAILS these tests, so a stopped stack can never look like
    # a pass; set SKIP_DB_TESTS=1 to skip them on purpose.
    if os.environ.get("SKIP_DB_TESTS") == "1":
        pytest.skip("SKIP_DB_TESTS=1")
    try:
        c = psycopg.connect(URL)  # not autocommit: everything below is one transaction
    except psycopg.OperationalError as err:
        pytest.fail(f"database not reachable: start the stack or set SKIP_DB_TESTS=1 ({err})")
    c.execute("INSERT INTO sources (name, base_url) VALUES (%s, 'http://zz.example')", (SOURCE,))
    yield c
    c.rollback()
    c.close()


def profiles_of(conn):
    return conn.execute(
        "SELECT p.name, p.region, p.updated_at, p.skills FROM profiles p"
        " JOIN profile_sources ps ON ps.profile_id = p.id"
        " JOIN source_records sr ON sr.id = ps.source_record_id"
        " WHERE sr.source = %s ORDER BY p.name", (SOURCE,)).fetchall()


def test_first_run_creates_profiles_and_records_the_run(conn):
    result = run_etl(conn, FakeConnector([raw(1), raw(2), raw(3)]), "full")
    assert result.counts["inserted"] == 3
    assert result.counts["profiles_created"] == 3
    rows = profiles_of(conn)
    assert [r[0] for r in rows] == ["Zzqetl Company 1", "Zzqetl Company 2", "Zzqetl Company 3"]
    assert rows[0][1] == "Crete"  # cleaned to the canonical region
    assert rows[0][2] == datetime(2026, 11, 11, 10, tzinfo=timezone.utc)  # the source's updated_at
    status, watermark, counts = conn.execute(
        "SELECT status, watermark, counts FROM sync_runs WHERE id = %s", (result.run_id,)).fetchone()
    assert status == "resolved"
    assert watermark == datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
    assert counts["fetched"] == 3


def test_rerun_creates_no_duplicates(conn):
    run_etl(conn, FakeConnector([raw(1), raw(2)]), "full")
    again = run_etl(conn, FakeConnector([raw(1), raw(2)]), "full")
    assert again.counts["unchanged"] == 2
    assert again.counts["profiles_created"] == again.counts["profiles_updated"] == 0
    assert len(profiles_of(conn)) == 2


def test_a_changed_record_updates_its_profile(conn):
    run_etl(conn, FakeConnector([raw(1)]), "full")
    version = conn.execute("SELECT data_version FROM pipeline_state").fetchone()[0]
    result = run_etl(conn, FakeConnector([raw(1, capabilities=["pastry", "chocolate"])]), "full")
    assert result.counts["updated"] == 1 and result.counts["profiles_updated"] == 1
    assert profiles_of(conn)[0][3] == ["pastry", "chocolate"]
    assert conn.execute("SELECT data_version FROM pipeline_state").fetchone()[0] == version + 1


def test_invalid_records_are_skipped_and_counted(conn):
    result = run_etl(conn, FakeConnector([raw(1), raw(2, category="Corporation")]), "full")
    assert (result.counts["inserted"], result.counts["invalid"]) == (1, 1)


def test_erased_records_are_not_imported(conn):
    secret = b"test-secret"
    conn.execute("INSERT INTO erasures (key_hmac) VALUES (%s)", (erasure_key(secret, SOURCE, "t-2"),))
    result = run_etl(conn, FakeConnector([raw(1), raw(2)]), "full", erasure_secret=secret)
    assert (result.counts["inserted"], result.counts["blocked"]) == (1, 1)
    assert [r[0] for r in profiles_of(conn)] == ["Zzqetl Company 1"]


def test_incremental_run_starts_from_the_last_watermark(conn):
    run_etl(conn, FakeConnector([raw(1), raw(2)]), "full")
    later = FakeConnector([raw(1), raw(2), raw(5)])
    result = run_etl(conn, later, "incremental")
    assert later.since_seen == [datetime(2026, 11, 12, 10, tzinfo=timezone.utc) - OVERLAP]
    assert result.counts["fetched"] == 2       # record 2 again (overlap) and the new record 5
    assert result.counts["inserted"] == 1
    assert len(profiles_of(conn)) == 3


def test_a_failed_run_is_marked_failed(conn):
    class Broken(FakeConnector):
        def pages(self, since, cursor=None):
            yield Page(records=[raw(1)], next_cursor="2")
            raise ConnectionError("source went away")

    with pytest.raises(ConnectionError):
        run_etl(conn, Broken([]), "full")
    status, error, counts = conn.execute(
        "SELECT status, error_code, counts FROM sync_runs WHERE source = %s", (SOURCE,)).fetchone()
    assert (status, error) == ("failed", "ConnectionError")
    assert counts["inserted"] == 1  # the first page was committed before the failure


def queued_row(conn, source=SOURCE, mode="full") -> str:
    """The row POST /sync inserts before it adds the job."""
    return conn.execute("INSERT INTO sync_runs (source, mode, status) VALUES (%s, %s, 'queued') RETURNING id::text",
                        (source, mode)).fetchone()[0]


def runs_of(conn):
    return conn.execute("SELECT count(*) FROM sync_runs WHERE source = %s", (SOURCE,)).fetchone()[0]


def test_a_queued_row_is_continued_not_duplicated(conn):
    row_id = queued_row(conn)
    result = run_etl(conn, FakeConnector([raw(1), raw(2)]), "full", sync_run_id=row_id)
    assert result.run_id == row_id
    assert runs_of(conn) == 1
    status, counts, started, finished = conn.execute(
        "SELECT status, counts, started_at, finished_at FROM sync_runs WHERE id = %s", (row_id,)).fetchone()
    assert status == "resolved" and counts["fetched"] == 2
    assert started is not None and finished is not None


def test_a_retry_after_failure_reuses_the_same_row(conn):
    class Broken(FakeConnector):
        def pages(self, since, cursor=None):
            raise ConnectionError("source went away")
            yield  # pragma: no cover

    row_id = queued_row(conn)
    with pytest.raises(ConnectionError):
        run_etl(conn, Broken([]), "full", sync_run_id=row_id)
    assert conn.execute("SELECT status FROM sync_runs WHERE id = %s", (row_id,)).fetchone()[0] == "failed"

    result = run_etl(conn, FakeConnector([raw(1)]), "full", sync_run_id=row_id)  # BullMQ retry
    assert result.run_id == row_id and runs_of(conn) == 1
    status, error = conn.execute("SELECT status, error_code FROM sync_runs WHERE id = %s", (row_id,)).fetchone()
    assert status == "resolved" and error is None  # the earlier failure is cleared


def test_an_unusable_sync_run_id_is_permanent(conn):
    from uuid import uuid4

    from pipeline.errors import PermanentError

    with pytest.raises(PermanentError):  # unknown id
        run_etl(conn, FakeConnector([raw(1)]), "full", sync_run_id=str(uuid4()))
    conn.execute("INSERT INTO sources (name, base_url) VALUES ('zz_other', 'http://zz.example')")
    other = queued_row(conn, source="zz_other")
    with pytest.raises(PermanentError):  # another source's row
        run_etl(conn, FakeConnector([raw(1)]), "full", sync_run_id=other)
    done = queued_row(conn)
    run_etl(conn, FakeConnector([raw(1)]), "full", sync_run_id=done)
    with pytest.raises(PermanentError):  # already resolved
        run_etl(conn, FakeConnector([raw(1)]), "full", sync_run_id=done)
