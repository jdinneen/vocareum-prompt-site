from __future__ import annotations

import sys
from pathlib import Path


# Make `app` importable when the site tests are run from the AIMktg repo root.
SITE_ROOT = Path(__file__).resolve().parents[1]
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))
