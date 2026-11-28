import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.connectors.source_b import SourceBConnector, to_normalized
from pipeline.etl import clean

FIXTURE = Path(__file__).parents[3] / "services/mock-sources/fixtures/source_b.json"

RAW = {
    "ref": " b-1 ",
    "fullName": "  Gaia   Creative ",
    "bio": "  Σχεδιασμός   λογοτύπων ",
    "field": " Design ",
    "area": "κρήτη",
    "expertise": ["branding", " Branding ", "   ", "Figma"],
    "offers": ["logo design"],
    "seeking": ["web development", "web development"],
    "speaks": ["EL", "en"],
    "homepage": None,
    "profileLink": "https://example.org/source_b/b-1",
    "modifiedAt": "2026-11-20T10:00:00+02:00",
    "hourlyRate": 45,
    "availability": "part-time",
}


def test_maps_and_cleans_a_record():
    r = to_normalized(RAW)
    assert (r.source, r.source_id, r.type) == ("source_b", "b-1", "freelancer")
    assert r.name == "Gaia Creative"
    assert r.description == "Σχεδιασμός λογοτύπων"
    assert (r.sector, r.region) == ("design", "Crete")
    assert r.skills == ["branding", "Figma"]
    assert r.needs == ["web development"]
    assert r.languages == ["el", "en"]
    assert str(r.original_url) == "https://example.org/source_b/b-1"
    assert r.source_updated_at.isoformat() == "2026-11-20T08:00:00+00:00"


def test_private_fields_are_never_kept():
    stored = to_normalized(RAW).model_dump(mode="json")  # exactly what load writes to raw
    assert "hourlyRate" not in stored and "availability" not in stored
    assert 45 not in stored.values() and "part-time" not in json.dumps(stored)


@pytest.mark.parametrize("change", [
    {"availability": "sometimes"},        # not one of the source's values
    {"hourlyRate": -5},
    {"fullName": ""},
    {"profileLink": "not a url"},
    {"unexpected": 1},
])
def test_rejects_records_that_break_the_source_b_schema(change):
    with pytest.raises(ValidationError):
        to_normalized({**RAW, **change})


def test_map_reports_the_bad_field_without_its_value():
    mapped = SourceBConnector("http://unused").map({**RAW, "hourlyRate": -5})
    assert mapped.record is None
    assert mapped.error == "invalid: hourlyRate"


def test_every_mock_source_b_record_maps():
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mapped = [to_normalized(r) for r in records]
    assert len(mapped) == len(records) > 500
    assert len({m.source_id for m in mapped}) == len(mapped)
    assert {m.type for m in mapped} == {"freelancer"}
    assert {m.region for m in mapped} <= set(clean.CANONICAL_REGIONS) | {None}


def test_the_export_is_cut_into_pages_with_cursors():
    export = [{"n": i} for i in range(250)]
    calls = []
    def fake_get(url, params=None):
        calls.append(url)
        return export

    pages = list(SourceBConnector("http://mock/", get=fake_get).pages(since=None))
    assert [len(p.records) for p in pages] == [100, 100, 50]
    assert [p.next_cursor for p in pages] == ["100", "200", None]
    assert calls == ["http://mock/b/export.json"]  # one download per run


def test_an_empty_export_gives_one_empty_page():
    pages = list(SourceBConnector("http://mock", get=lambda url, params=None: []).pages(None))
    assert [(p.records, p.next_cursor) for p in pages] == [([], None)]
