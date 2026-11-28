"""Connector for source B, the freelancer platform: one full export, GET /b/export.json.

Source B has no paging and no updated_since, so every run downloads the whole
export. Partial sync relies on the content hash instead: a record that did not
change is counted as unchanged and its profile is not touched. The export is cut
into pages here so each page still commits with the run's cursor (rule 1).
"""

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from pipeline.connectors.base import Mapped, Page
from pipeline.connectors.http import get_json
from pipeline.etl import clean
from pipeline.generated.normalized_record import NormalizedRecord
from pipeline.generated.source_b_record import SourceBRecord

SOURCE = "source_b"
PAGE_SIZE = 100


def to_normalized(raw: dict[str, Any]) -> NormalizedRecord:
    """Validate a source B record, map its fields and clean them. Raises ValidationError.

    hourlyRate and availability are validated as part of the source's shape but never
    mapped: they are not in the common schema and must not be stored (rule 2).
    """
    b = SourceBRecord.model_validate(raw)
    return NormalizedRecord.model_validate({
        "source": SOURCE,
        "source_id": b.ref.strip(),
        "original_url": str(b.profileLink),
        "source_updated_at": b.modifiedAt.astimezone(timezone.utc),
        "type": "freelancer",
        "name": clean.text(b.fullName),
        "description": clean.text(b.bio) or "",
        "sector": clean.sector(b.field),
        "region": clean.region(b.area),
        "skills": clean.text_list(b.expertise),
        "services": clean.text_list(b.offers),
        "needs": clean.text_list(b.seeking),
        "languages": clean.languages(b.speaks),
        "website": clean.web_url(b.homepage),
    })


class SourceBConnector:
    source = SOURCE

    def __init__(self, base_url: str, page_size: int = PAGE_SIZE, get=get_json):
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self._get = get

    def pages(self, since: datetime | None, cursor: str | None = None) -> Iterator[Page]:
        # `since` cannot narrow a full export; the hash comparison in load does that job.
        records = self._get(f"{self.base_url}/b/export.json")
        if not isinstance(records, list):
            raise ValueError("source B export is not a JSON array")
        start = int(cursor or 0)
        if start >= len(records):  # an empty export still makes one (empty) page
            yield Page(records=[], next_cursor=None)
            return
        for offset in range(start, len(records), self.page_size):
            end = offset + self.page_size
            yield Page(records=records[offset:end], next_cursor=str(end) if end < len(records) else None)

    def map(self, raw: dict[str, Any]) -> Mapped:
        try:
            return Mapped(record=to_normalized(raw))
        except ValidationError as err:
            # Field names only: raw values may hold personal data (rule 29).
            fields = sorted({".".join(map(str, e["loc"])) for e in err.errors()})
            return Mapped(error="invalid: " + ", ".join(fields))
