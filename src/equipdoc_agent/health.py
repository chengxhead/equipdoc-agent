from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    required: bool
    detail: str


def _path_check(name: str, path: Path, required: bool, *, public: bool) -> HealthCheck:
    detail = path.name if public else str(path)
    return HealthCheck(name=name, ok=path.exists(), required=required, detail=detail)


def collect_health(settings: Settings, *, public: bool = False) -> dict:
    settings.ensure_runtime_dirs()
    checks = [
        _path_check("sample_signal", settings.sample_root / "test_signal.npy", True, public=public),
        _path_check("upload_root", settings.upload_root, True, public=public),
        _path_check("rag_chunks", settings.rag_chunks_path, settings.rag_enabled, public=public),
        _path_check(
            "bearing_model", settings.bearing_model_path, not settings.demo_mode, public=public
        ),
        _path_check(
            "bearing_norm", settings.bearing_norm_path, not settings.demo_mode, public=public
        ),
        _path_check("rag_vector_db", settings.rag_db_dir, False, public=public),
    ]
    checks.append(
        HealthCheck(
            name="llm_configuration",
            ok=bool(settings.llm_base_url and settings.llm_model),
            required=not settings.demo_mode,
            detail=(
                f"{settings.llm_model} configured"
                if public
                else f"{settings.llm_model} @ {settings.llm_base_url}"
            ),
        )
    )
    ready = all(item.ok for item in checks if item.required)
    return {
        "ready": ready,
        "mode": settings.mode_name,
        "agentic": {
            "enabled": not settings.demo_mode and settings.agentic_mode,
            "max_steps": settings.agent_max_steps,
        },
        "checks": [asdict(item) for item in checks],
        "note": "Service reachability is not checked unless the application sends a request.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check EquipDoc-Agent startup prerequisites.")
    parser.add_argument("--strict", action="store_true", help="Return a non-zero code when required checks fail.")
    args = parser.parse_args()
    report = collect_health(Settings.from_env())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
