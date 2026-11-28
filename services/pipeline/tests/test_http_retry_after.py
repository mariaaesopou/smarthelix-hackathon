import datetime
import email.utils
import urllib.error

import pytest

from pipeline.connectors import http
from pipeline.connectors.http import SourceUnavailable, parse_retry_after


def test_seconds_and_garbage():
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after("-5") == 0.0
    assert parse_retry_after("soon") is None
    assert parse_retry_after(None) is None


def test_http_date():
    when = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=90)
    assert 80 < parse_retry_after(email.utils.format_datetime(when, usegmt=True)) <= 90
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=90)
    assert parse_retry_after(email.utils.format_datetime(past, usegmt=True)) == 0.0


def test_source_unavailable_carries_the_last_hint(monkeypatch):
    def boom(url, timeout):
        raise urllib.error.HTTPError(url, 429, "slow down", {"Retry-After": "7"}, None)

    monkeypatch.setattr(http.urllib.request, "urlopen", boom)
    with pytest.raises(SourceUnavailable) as exc:
        http.get_json("http://x/y", attempts=2, sleep=lambda s: None)
    assert exc.value.retry_after_s == 7.0
