"""Values shared with the TypeScript side, read from packages/shared/constants.json."""

import json
from pathlib import Path

_FILE = Path(__file__).resolve().parents[4] / "packages" / "shared" / "constants.json"
_DATA = json.loads(_FILE.read_text(encoding="utf-8"))

K_ERASURE: int = _DATA["advisoryLocks"]["K_ERASURE"]
EXIT_SUCCESS: int = _DATA["exitCodes"]["success"]
EXIT_PERMANENT: int = _DATA["exitCodes"]["permanent"]
EXIT_RETRYABLE: int = _DATA["exitCodes"]["retryable"]
