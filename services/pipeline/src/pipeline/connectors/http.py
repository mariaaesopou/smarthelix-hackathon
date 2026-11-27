"""A small JSON client with retries; the standard library is enough for the sources."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

RETRYABLE = {429, 500, 502, 503, 504}


class SourceUnavailable(Exception):
    """The source kept failing; the run may be retried later (exit code 75)."""


def get_json(url: str, params: dict[str, Any] | None = None, *, attempts: int = 5,
             timeout: float = 30, sleep=time.sleep) -> Any:
    """GET url and parse JSON. Retries 429 and 5xx, honouring Retry-After, with backoff."""
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(full, timeout=timeout) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code not in RETRYABLE or attempt == attempts:
                if err.code in RETRYABLE:
                    raise SourceUnavailable(f"{err.code} from {url}") from err
                raise
            wait = float(err.headers.get("Retry-After") or 2 ** attempt)
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == attempts:
                raise SourceUnavailable(f"cannot reach {url}") from err
            wait = 2 ** attempt
        sleep(min(wait, 60))
    raise AssertionError("unreachable")
