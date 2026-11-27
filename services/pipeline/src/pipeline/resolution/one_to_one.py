"""Resolution, first version: one source record makes one profile (rule 4).

Cross-source deduplication (rules 5-7) replaces this on day 7; the input stays
the same: records whose resolved_hash differs from their hash.
"""

from dataclasses import dataclass

from psycopg import Connection

from pipeline.constants import K_ERASURE

PENDING_SQL = """
SELECT sr.id, sr.raw, sr.source_updated_at, ps.profile_id
FROM source_records sr
LEFT JOIN profile_sources ps ON ps.source_record_id = sr.id
WHERE sr.deleted_at IS NULL AND sr.resolved_hash IS DISTINCT FROM sr.hash
ORDER BY sr.id
FOR UPDATE OF sr
"""

FIELDS = ("type", "name", "description", "sector", "region", "skills", "services",
          "needs", "languages", "website")

UPDATE_SQL = f"""
UPDATE profiles SET {", ".join(f"{f} = %({f})s" for f in FIELDS)},
       updated_at = coalesce(%(updated_at)s, now())
WHERE id = %(profile_id)s
"""

INSERT_SQL = f"""
INSERT INTO profiles ({", ".join(FIELDS)}, updated_at)
VALUES ({", ".join(f"%({f})s" for f in FIELDS)}, coalesce(%(updated_at)s, now()))
RETURNING id
"""


@dataclass
class ResolutionResult:
    created: int = 0
    updated: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)


def resolve(conn: Connection) -> ResolutionResult:
    """Build or refresh the profile of every changed record, in one transaction.

    When anything changed, data_version goes up in the same transaction (rule 10),
    which later tells the ML debounce that the Spark results are stale.
    """
    result = ResolutionResult()
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock_shared(%s)", (K_ERASURE,))
        for record_id, raw, updated_at, profile_id in conn.execute(PENDING_SQL).fetchall():
            values = {f: raw[f] for f in FIELDS} | {"updated_at": updated_at}
            if profile_id:
                conn.execute(UPDATE_SQL, values | {"profile_id": profile_id})
                result.updated += 1
            else:
                (new_id,) = conn.execute(INSERT_SQL, values).fetchone()
                conn.execute(
                    "INSERT INTO profile_sources (source_record_id, profile_id, match_method, confidence)"
                    " VALUES (%s, %s, 'new', 1)", (record_id, new_id))
                result.created += 1
            conn.execute("UPDATE source_records SET resolved_hash = hash WHERE id = %s", (record_id,))
        if result.changed:
            conn.execute(
                "UPDATE pipeline_state SET data_version = data_version + 1, last_change_at = now(),"
                " dirty_since = coalesce(dirty_since, now())")
    return result
