"""What every source connector provides, so the ETL run does not depend on the source."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from pipeline.generated.normalized_record import NormalizedRecord


@dataclass
class Page:
    """One batch of raw records and where the next batch starts."""

    records: list[dict[str, Any]]
    next_cursor: str | None
    """Opaque position of the next page; None after the last page."""


@dataclass
class Mapped:
    """A raw record mapped to the common schema, or the reason it was skipped."""

    record: NormalizedRecord | None = None
    error: str | None = field(default=None)


class Connector(Protocol):
    source: str
    """Name in the sources table, such as source_a."""

    def pages(self, since: datetime | None, cursor: str | None = None) -> Iterator[Page]:
        """Raw records, page by page. `since` limits them to records changed since then."""
        ...

    def map(self, raw: dict[str, Any]) -> Mapped:
        """Validate one raw record, map it to NormalizedRecord and clean it."""
        ...
