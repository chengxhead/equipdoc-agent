from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from equipdoc_agent.config import Settings
from equipdoc_agent.tools import analyze_bearing_signal


def main() -> None:
    settings = Settings.from_env(ROOT)
    if not settings.demo_mode:
        raise SystemExit("Set EQUIPDOC_DEMO_MODE=true before running the demo smoke test.")
    result = analyze_bearing_signal(settings.sample_root / "test_signal.npy", settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

