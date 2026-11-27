import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.connectors.source_a import SourceAConnector, to_normalized
from pipeline.etl import clean

FIXTURE = Path(__file__).parents[3] / "services/mock-sources/fixtures/source_a.json"

RAW = {
    "id": " a-1 ",
    "company_name": "  Ζαχαροπλαστείο   Gaia ",
    "category": "Startup",
    "summary": "  Γλυκά   κατά παραγγελία ",
    "industry": " Food ",
    "location": "αττική",
    "capabilities": ["pastry", " Pastry ", "   ", "baking"],  # blank items are cleaned away
    "products": ["custom cakes"],
    "looking_for": ["web development", "web development"],
    "languages": ["EL", "en", "el"],
    "website": None,
    "profile_url": "https://example.org/source_a/a-1",
    "last_modified": "2026-11-20T10:00:00+02:00",
}


def test_maps_and_cleans_a_record():
    r = to_normalized(RAW)
    assert (r.source, r.source_id, r.type) == ("source_a", "a-1", "young_entrepreneur")
    assert r.name == "Ζαχαροπλαστείο Gaia"
    assert r.description == "Γλυκά κατά παραγγελία"
    assert (r.sector, r.region) == ("food", "Attica")
    assert r.skills == ["pastry", "baking"]
    assert r.needs == ["web development"]
    assert r.languages == ["el", "en"]
    assert str(r.original_url) == "https://example.org/source_a/a-1"
    assert r.source_updated_at.isoformat() == "2026-11-20T08:00:00+00:00"  # stored in UTC


def test_sme_category():
    assert to_normalized({**RAW, "category": "SME"}).type == "sme"


@pytest.mark.parametrize("change", [
    {"category": "Corporation"},          # not SME or Startup
    {"company_name": ""},                 # name required
    {"profile_url": "not a url"},
    {"unexpected": 1},                    # field source A does not send
])
def test_rejects_records_that_break_the_source_a_schema(change):
    with pytest.raises(ValidationError):
        to_normalized({**RAW, **change})


def test_map_reports_the_bad_field_without_its_value():
    mapped = SourceAConnector("http://unused").map({**RAW, "category": "Corporation"})
    assert mapped.record is None
    assert mapped.error == "invalid: category"


@pytest.mark.parametrize("raw, expected", [
    ("Attica", "Attica"), ("ATTIKI", "Attica"), ("Αττική", "Attica"), ("κρήτη", "Crete"),
    ("Νότιο Αιγαίο", "South Aegean"), ("Atlantis", "Atlantis"), ("  ", None), (None, None),
])
def test_region_names_become_canonical(raw, expected):
    assert clean.region(raw) == expected


def test_web_url_keeps_only_http_links():
    assert clean.web_url("https://shop.example") == "https://shop.example"
    assert clean.web_url("ftp://shop.example") is None
    assert clean.web_url("shop.example") is None


def test_every_mock_source_a_record_maps():
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mapped = [to_normalized(r) for r in records]
    assert len(mapped) == len(records) > 1000
    assert len({m.source_id for m in mapped}) == len(mapped)
    assert {m.region for m in mapped} <= set(clean.CANONICAL_REGIONS) | {None}


def test_pages_follow_next_page_and_pass_updated_since():
    calls = []
    def fake_get(url, params):
        calls.append(params)
        return {"data": [{"page": params["page"]}], "next_page": 2 if params["page"] == 1 else None}

    from datetime import datetime, timezone
    pages = list(SourceAConnector("http://mock/", get=fake_get).pages(
        datetime(2026, 11, 20, 10, tzinfo=timezone.utc)))
    assert [p.next_cursor for p in pages] == ["2", None]
    assert calls[0] == {"page": 1, "per_page": 100, "updated_since": "2026-11-20T10:00:00Z"}
    assert calls[1]["page"] == 2
