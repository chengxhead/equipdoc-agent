from __future__ import annotations

import re
import time

from .config import Settings


STAGED_SIGNAL_PATTERN = re.compile(r"^[0-9a-f]{32}\.npy$")


def cleanup_stale_uploads(settings: Settings, *, now: float | None = None) -> dict[str, int]:
    """Remove expired app-staged signals without touching user-named files or symlinks."""
    settings.ensure_runtime_dirs()
    current_time = time.time() if now is None else float(now)
    removed = 0
    failed = 0
    for candidate in settings.upload_root.iterdir():
        if not STAGED_SIGNAL_PATTERN.fullmatch(candidate.name) or candidate.is_symlink():
            continue
        try:
            if not candidate.is_file():
                continue
            age_seconds = current_time - candidate.stat().st_mtime
            if age_seconds < settings.upload_ttl_seconds:
                continue
            candidate.unlink()
            removed += 1
        except OSError:
            failed += 1
    return {"removed": removed, "failed": failed}
