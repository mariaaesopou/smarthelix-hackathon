"""Connector for source A, the SME platform: GET /a/profiles, paged, with updated_since."""

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from pipeline.connectors.base import Mapped, Page
from pipeline.connectors.http import get_json
from pipeline.etl import clean
from pipeline.generated.normalized_record import NormalizedRecord
from pipeline.generated.source_a_record import Category, SourceARecord

SOURCE = "source_a"
PER_PAGE = 100  # the most source A allows
TYPES = {Category.SME: "sme", Category.Startup: "young_entrepreneur"}


def to_normalized(raw: dict[str, Any]) -> NormalizedRecord:
    """Validate a source A record, map its fields and clean them. Raises ValidationError."""
    a = SourceARecord.model_validate(raw)
    return NormalizedRecord.model_validate({
        "source": SOURCE,
        "source_id": a.id.strip(),
        "original_url": str(a.profile_url),
        "source_updated_at": a.last_modified.astimezone(timezone.utc),
        "type": TYPES[a.category],
        "name": clean.text(a.company_name),
        "description": clean.text(a.summary) or "",
        "sector": clean.sector(a.industry),
        "region": clean.region(a.location),
        "skills": clean.text_list(a.capabilities),
        "services": clean.text_list(a.products),
        "needs": clean.text_list(a.looking_for),
        "languages": clean.languages(a.languages),
        "website": clean.web_url(a.website),
    })


class SourceAConnector:
    source = SOURCE

    def __init__(self, base_url: str, per_page: int = PER_PAGE, get=get_json):
        self.base_url = base_url.rstrip("/")
        self.per_page = per_page
        self._get = get

    def pages(self, since: datetime | None, cursor: str | None = None) -> Iterator[Page]:
        page = int(cursor or 1)
        while True:
            params: dict[str, Any] = {"page": page, "per_page": self.per_page}
            if since:
                params["updated_since"] = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            body = self._get(f"{self.base_url}/a/profiles", params)
            next_page = body.get("next_page")
            yield Page(records=body["data"], next_cursor=str(next_page) if next_page else None)
            if not next_page:
                return
            page = next_page

    def map(self, raw: dict[str, Any]) -> Mapped:
        try:
            return Mapped(record=to_normalized(raw))
        except ValidationError as err:
            # Field names only: raw values may hold personal data (rule 29).
            fields = sorted({".".join(map(str, e["loc"])) for e in err.errors()})
            return Mapped(error="invalid: " + ", ".join(fields))
