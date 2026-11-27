"""Cleaning rules every connector applies before the common schema is validated."""

import re
import unicodedata
from collections.abc import Iterable
from urllib.parse import urlsplit

# One canonical spelling per Greek administrative region. Keys are matched after
# normalise(), so case, accents and punctuation do not matter.
CANONICAL_REGIONS = [
    "Attica", "Central Greece", "Central Macedonia", "Crete", "Eastern Macedonia and Thrace",
    "Epirus", "Ionian Islands", "North Aegean", "Peloponnese", "South Aegean", "Thessaly",
    "Western Greece", "Western Macedonia",
]
_REGION_ALIASES = {
    "attiki": "Attica", "αττικη": "Attica",
    "sterea ellada": "Central Greece", "στερεα ελλαδα": "Central Greece",
    "kentriki makedonia": "Central Macedonia", "κεντρικη μακεδονια": "Central Macedonia",
    "kriti": "Crete", "κρητη": "Crete",
    "anatoliki makedonia kai thraki": "Eastern Macedonia and Thrace",
    "ανατολικη μακεδονια και θρακη": "Eastern Macedonia and Thrace",
    "ipeiros": "Epirus", "ηπειροσ": "Epirus",
    "ionia nisia": "Ionian Islands", "ιονια νησια": "Ionian Islands",
    "voreio aigaio": "North Aegean", "βορειο αιγαιο": "North Aegean",
    "peloponnisos": "Peloponnese", "πελοποννησοσ": "Peloponnese",
    "notio aigaio": "South Aegean", "νοτιο αιγαιο": "South Aegean",
    "thessalia": "Thessaly", "θεσσαλια": "Thessaly",
    "dytiki ellada": "Western Greece", "δυτικη ελλαδα": "Western Greece",
    "dytiki makedonia": "Western Macedonia", "δυτικη μακεδονια": "Western Macedonia",
}


def normalise(value: str) -> str:
    """Lower case, no accents, final sigma as sigma, single spaces: like f_norm in SQL."""
    text = unicodedata.normalize("NFD", value)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower().replace("ς", "σ")
    return " ".join(re.findall(r"\w+", text))


_REGIONS = {normalise(r): r for r in CANONICAL_REGIONS} | _REGION_ALIASES


def text(value: str | None) -> str | None:
    """Trimmed text with single spaces; empty becomes None."""
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def text_list(values: Iterable[str] | None) -> list[str]:
    """Trimmed, non-empty items, without case-insensitive duplicates, in their first order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        item = text(value)
        if item and (key := item.casefold()) not in seen:
            seen.add(key)
            out.append(item)
    return out


def region(value: str | None) -> str | None:
    """The canonical region name; an unknown region is kept as cleaned text."""
    cleaned = text(value)
    return _REGIONS.get(normalise(cleaned), cleaned) if cleaned else None


def sector(value: str | None) -> str | None:
    cleaned = text(value)
    return cleaned.lower() if cleaned else None


def languages(values: Iterable[str] | None) -> list[str]:
    return text_list(v.lower() for v in values or [])


def web_url(value: object) -> str | None:
    """An http(s) URL with a host, or None."""
    cleaned = text(str(value)) if value is not None else None
    if not cleaned:
        return None
    parts = urlsplit(cleaned)
    return cleaned if parts.scheme in ("http", "https") and parts.netloc else None
