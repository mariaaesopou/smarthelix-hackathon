"""Load: upsert normalised records into source_records on (source, source_id)."""

import hashlib
import hmac
import json
from typing import Any, Literal

from psycopg import Connection
from psycopg.types.json import Jsonb

from pipeline.generated.normalized_record import NormalizedRecord

Outcome = Literal["inserted", "updated", "unchanged", "blocked"]

# The CTE reads the row as it was before this statement, so we can tell an insert,
# a real change and an unchanged record apart. A record that comes back after a
# deletion gets resolved_hash NULL, so resolution looks at it again (rule 4).
UPSERT_SQL = """
WITH prev AS (
  SELECT hash, deleted_at FROM source_records
  WHERE source = %(source)s AND source_id = %(source_id)s
)
INSERT INTO source_records
  (source, source_id, raw, hash, original_url, source_updated_at, last_seen_run_id)
VALUES (%(source)s, %(source_id)s, %(raw)s, %(hash)s, %(original_url)s,
        %(source_updated_at)s, %(run_id)s)
ON CONFLICT (source, source_id) DO UPDATE SET
  raw = EXCLUDED.raw,
  hash = EXCLUDED.hash,
  original_url = EXCLUDED.original_url,
  source_updated_at = EXCLUDED.source_updated_at,
  fetched_at = now(),
  last_seen_run_id = EXCLUDED.last_seen_run_id,
  resolved_hash = CASE WHEN source_records.deleted_at IS NOT NULL THEN NULL
                       ELSE source_records.resolved_hash END,
  deleted_at = NULL
RETURNING (SELECT hash FROM prev) AS prev_hash, (SELECT deleted_at FROM prev) AS prev_deleted
"""


def record_hash(raw: dict[str, Any]) -> str:
    """Fingerprint of a normalised record; it changes only when a stored value changes."""
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def erasure_key(secret: bytes, source: str, source_id: str) -> bytes:
    """HMAC of an unambiguous (length-prefixed) encoding of the pair (rule 28)."""
    message = f"{len(source)}:{source}{len(source_id)}:{source_id}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).digest()


def is_erased(conn: Connection, secret: bytes | None, source: str, source_id: str) -> bool:
    if not secret:
        return False
    key = erasure_key(secret, source, source_id)
    return conn.execute("SELECT 1 FROM erasures WHERE key_hmac = %s", (key,)).fetchone() is not None


def upsert(conn: Connection, record: NormalizedRecord, run_id: str,
           erasure_secret: bytes | None) -> Outcome:
    """Store one record. Only the allowlisted NormalizedRecord fields go into raw (rule 2)."""
    if is_erased(conn, erasure_secret, record.source, record.source_id):
        return "blocked"
    raw = record.model_dump(mode="json")
    digest = record_hash(raw)
    prev_hash, prev_deleted = conn.execute(UPSERT_SQL, {
        "source": record.source,
        "source_id": record.source_id,
        "raw": Jsonb(raw),
        "hash": digest,
        "original_url": str(record.original_url),
        "source_updated_at": record.source_updated_at,
        "run_id": run_id,
    }).fetchone()
    if prev_hash is None:
        return "inserted"
    return "unchanged" if prev_hash == digest and prev_deleted is None else "updated"
