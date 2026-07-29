from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from equipdoc_agent.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def _request_json(url: str, api_key: str, payload: dict | None, timeout: float) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _gpu_inventory() -> list[dict[str, str]]:
    command = [
        "nvidia-smi",
        "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    rows = []
    for line in completed.stdout.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) == 3:
            rows.append(
                {"name": values[0], "memory_total_mb": values[1], "driver_version": values[2]}
            )
    return rows


def main() -> None:
    settings = Settings.from_env(ROOT)
    parser = argparse.ArgumentParser(description="Check an OpenAI-compatible Full-mode service.")
    parser.add_argument("--base-url", default=settings.llm_base_url)
    parser.add_argument("--model", default=settings.llm_model)
    parser.add_argument("--api-key", default=settings.llm_api_key)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    started = time.perf_counter()
    try:
        models_payload = _request_json(
            f"{base_url}/models", args.api_key, payload=None, timeout=args.timeout
        )
        model_ids = [item.get("id") for item in models_payload.get("data", [])]
        if args.model not in model_ids:
            raise RuntimeError(f"Configured model {args.model!r} is not listed: {model_ids}")
        chat_payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": "只回复 READY"}],
            "temperature": 0,
            "max_tokens": 8,
        }
        chat_result = _request_json(
            f"{base_url}/chat/completions",
            args.api_key,
            payload=chat_payload,
            timeout=args.timeout,
        )
        content = str(chat_result.get("choices", [{}])[0].get("message", {}).get("content", ""))
        ready = bool(content.strip())
        error = None
    except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, KeyError) as exc:
        model_ids = []
        content = ""
        ready = False
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ready": ready,
        "base_url": base_url,
        "configured_model": args.model,
        "listed_models": model_ids,
        "probe_latency_seconds": elapsed,
        "probe_response": content[:80],
        "gpu_inventory": _gpu_inventory(),
        "error": error,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: {args.output}")
    if not ready:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
