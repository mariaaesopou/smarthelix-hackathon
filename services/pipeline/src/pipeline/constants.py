"""Values shared with the TypeScript side, read from packages/shared/constants.json.

Exit codes live in errors.py, next to the exceptions that produce them.
"""

import json
from pathlib import Path

_FILE = Path(__file__).resolve().parents[4] / "packages" / "shared" / "constants.json"
_DATA = json.loads(_FILE.read_text(encoding="utf-8"))

K_ERASURE: int = _DATA["advisoryLocks"]["K_ERASURE"]
K_ML: int = _DATA["advisoryLocks"]["K_ML"]
