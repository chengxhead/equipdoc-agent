from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import statistics
import subprocess
import time
import urllib.request
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from equipdoc_agent.agent import build_graph
from equipdoc_agent.agent.knowledge_answer import extract_citations
from equipdoc_agent.agent.planning import ALLOWED_INTENTS, ALLOWED_TOOLS
from equipdoc_agent.config import Settings


ROOT = Path(__file__).resolve().parents[1]
REVIEW_VALUES = {"none", "approve", "reject"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    if not cases:
        raise ValueError("Agentic evaluation file is empty.")
    seen_ids: set[str] = set()
    for case in cases:
        case_id = str(case.get("id", "")).strip()
        if not case_id or case_id in seen_ids:
            raise ValueError(f"Invalid or duplicate case id: {case_id!r}")
        seen_ids.add(case_id)
        if not str(case.get("group", "")).strip():
            raise ValueError(f"{case_id}: group is required")
        turns = case.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ValueError(f"{case_id}: turns must be a non-empty list")
        for index, turn in enumerate(turns, start=1):
            prefix = f"{case_id} turn {index}"
            if not isinstance(turn, dict) or not str(turn.get("question", "")).strip():
                raise ValueError(f"{prefix}: question is required")
            expected_intent = turn.get("expected_intent")
            if expected_intent is not None and expected_intent not in ALLOWED_INTENTS:
                raise ValueError(f"{prefix}: unknown expected_intent {expected_intent!r}")
            review = turn.get("review", "none")
            if review not in REVIEW_VALUES:
                raise ValueError(f"{prefix}: invalid review value {review!r}")
            expected_tools = turn.get("expected_tools", [])
            allowed_tools = turn.get("allowed_tools", [])
            if not isinstance(expected_tools, list) or not isinstance(allowed_tools, list):
                raise ValueError(f"{prefix}: tool fields must be lists")
            unknown_tools = set(expected_tools + allowed_tools).difference(ALLOWED_TOOLS)
            if unknown_tools:
                raise ValueError(f"{prefix}: unknown tools {sorted(unknown_tools)}")
            if not set(expected_tools).issubset(allowed_tools):
                raise ValueError(f"{prefix}: expected_tools must be allowed")
            if not isinstance(turn.get("required_keywords", []), list):
                raise ValueError(f"{prefix}: required_keywords must be a list")
            if not isinstance(turn.get("memory_has", []), list):
                raise ValueError(f"{prefix}: memory_has must be a list")


def _service_models(base_url: str, api_key: str, timeout: float) -> list[str]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [str(item.get("id")) for item in payload.get("data", [])]


def _command_output(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _environment() -> dict[str, Any]:
    packages = {}
    for name in ("langchain-openai", "langgraph", "numpy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    gpu_rows = _command_output(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "git_commit": _command_output(["git", "rev-parse", "HEAD"]),
        "gpu_inventory": gpu_rows.splitlines() if gpu_rows else [],
    }


def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
    value = getattr(first, "value", first)
    return value if isinstance(value, dict) else None


def _last_message(result: dict[str, Any]):
    messages = result.get("messages", [])
    return messages[-1] if messages else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [bool(row[key]) for row in rows if row.get(key) is not None]
    return None if not values else sum(values) / len(values)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)
    latencies = [float(row["latency_seconds"]) for row in rows if row.get("success")]

    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "turn_count": len(items),
            "success_rate": _rate(items, "success"),
            "case_pass_rate": _rate(items, "passed"),
            "intent_accuracy": _rate(items, "intent_ok"),
            "expected_tool_coverage": _rate(items, "expected_tools_ok"),
            "tool_allowlist_compliance": _rate(items, "allowed_tools_ok"),
            "review_gate_compliance": _rate(items, "review_ok"),
            "review_payload_privacy_rate": _rate(items, "privacy_ok"),
            "clarification_compliance": _rate(items, "clarification_ok"),
            "citation_validity_rate": _rate(items, "citations_ok"),
            "grounded_answer_guard_rate": _rate(items, "answer_guard_ok"),
            "memory_retention_rate": _rate(items, "memory_ok"),
            "required_keyword_case_pass_rate": _rate(items, "keywords_ok"),
        }

    return {
        "overall": {
            **block(rows),
            "latency_mean_seconds": statistics.mean(latencies) if latencies else None,
            "latency_p50_seconds": _percentile(latencies, 50),
            "latency_p95_seconds": _percentile(latencies, 95),
            "average_tool_steps": (
                statistics.mean(row["tool_step_count"] for row in rows)
                if rows
                else None
            ),
        },
        "by_group": {
            group: block(items) for group, items in sorted(grouped.items())
        },
    }


def main() -> None:
    base_settings = Settings.from_env(ROOT)
    parser = argparse.ArgumentParser(
        description="Evaluate the P2.1 Agentic graph with a real local Qwen service."
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=ROOT / "data/eval/agentic_smoke.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts/p2_1/agentic_smoke.json",
    )
    parser.add_argument("--base-url", default=base_settings.llm_base_url)
    parser.add_argument("--model", default=base_settings.llm_model)
    parser.add_argument("--api-key", default=base_settings.llm_api_key)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--min-case-pass-rate", type=float, default=None)
    args = parser.parse_args()

    cases = _load_jsonl(args.eval_file)
    _validate_cases(cases)
    if args.limit > 0:
        cases = cases[: args.limit]
    planned_turns = sum(len(case["turns"]) for case in cases)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "valid": True,
                    "case_count": len(cases),
                    "turn_count": planned_turns,
                    "eval_sha256": _sha256(args.eval_file),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    model_ids = _service_models(args.base_url, args.api_key, args.timeout)
    if args.model not in model_ids:
        raise SystemExit(
            f"Configured model {args.model!r} is not listed by service: {model_ids}"
        )
    settings = replace(
        base_settings,
        demo_mode=False,
        agentic_mode=True,
        agent_max_steps=max(1, min(4, args.max_steps)),
        llm_base_url=args.base_url.rstrip("/"),
        llm_model=args.model,
        llm_api_key=args.api_key,
        llm_timeout_seconds=args.timeout,
    )
    sample_path = (settings.sample_root / "test_signal.npy").resolve()
    if not sample_path.exists():
        raise SystemExit(f"Sample signal is missing: {sample_path}")
    graph = build_graph(settings)
    corpus = {
        item["chunk_id"]: item
        for item in _load_jsonl(settings.rag_chunks_path)
    }

    rows: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases, start=1):
        thread_id = f"p2_1_{case['id']}_{uuid4().hex}"
        config = {"configurable": {"thread_id": thread_id}}
        for turn_index, turn in enumerate(case["turns"], start=1):
            print(
                f"[{case_index}/{len(cases)} turn {turn_index}] {case['id']}",
                flush=True,
            )
            payload: dict[str, Any] = {
                "messages": [HumanMessage(content=turn["question"])]
            }
            if turn.get("use_signal"):
                payload["signal_path"] = str(sample_path)
            started = time.perf_counter()
            try:
                result = graph.invoke(payload, config=config)
                review_payload = _interrupt_payload(result)
                review_expected = turn.get("review", "none")
                if review_payload and review_expected in {"approve", "reject"}:
                    result = graph.invoke(
                        Command(resume=review_expected),
                        config=config,
                    )
                latency = time.perf_counter() - started
                message = _last_message(result)
                answer = str(getattr(message, "content", ""))
                observations = list(result.get("tool_observations") or [])
                actual_tools = [
                    str(item.get("_tool_name"))
                    for item in observations
                    if item.get("_tool_name")
                ]
                plan = result.get("current_plan") or {}
                actual_intent = str(
                    plan.get("intent")
                    or (
                        "safety_boundary"
                        if result.get("safety_decision")
                        else "unknown"
                    )
                )
                expected_intent = turn.get("expected_intent")
                intent_ok = (
                    None
                    if expected_intent is None
                    else actual_intent == expected_intent
                )
                expected_tools = set(turn.get("expected_tools", []))
                allowed_tools = set(turn.get("allowed_tools", []))
                expected_tools_ok = expected_tools.issubset(actual_tools)
                allowed_tools_ok = set(actual_tools).issubset(allowed_tools)
                review_ok = (
                    bool(review_payload)
                    if review_expected in {"approve", "reject"}
                    else not bool(review_payload)
                )
                serialized_review = json.dumps(
                    review_payload or {},
                    ensure_ascii=False,
                )
                privacy_ok = (
                    "signal_path" not in serialized_review
                    and str(settings.project_root) not in serialized_review
                )
                clarification_ok = (
                    "需要补充信息" in answer
                    if expected_intent == "clarification"
                    else None
                )
                citations = extract_citations(answer)
                citation_checks = [
                    chunk_id in corpus
                    and corpus[chunk_id].get("doc_id") == doc_id
                    for doc_id, chunk_id in citations
                ]
                require_citation = bool(turn.get("require_citation"))
                citations_ok = (
                    bool(citations) and all(citation_checks)
                    if require_citation
                    else None
                )
                response_metadata = getattr(message, "response_metadata", None) or {}
                agentic_metadata = response_metadata.get("equipdoc_agentic") or {}
                answer_guard = agentic_metadata.get("answer_guard") or {}
                final_guard = answer_guard.get("final_citation_validation") or {}
                answer_guard_ok = (
                    bool(final_guard.get("valid"))
                    if require_citation
                    else None
                )
                memory = result.get("session_memory") or {}
                required_memory = list(turn.get("memory_has", []))
                memory_ok = (
                    all(
                        key in memory
                        and memory[key] is not None
                        and memory[key] != ""
                        for key in required_memory
                    )
                    if required_memory
                    else None
                )
                required_keywords = list(turn.get("required_keywords", []))
                keywords_ok = all(keyword in answer for keyword in required_keywords)
                applicable_checks = [
                    check
                    for check in (
                        intent_ok,
                        expected_tools_ok,
                        allowed_tools_ok,
                        review_ok,
                        privacy_ok,
                        clarification_ok,
                        citations_ok,
                        answer_guard_ok,
                        memory_ok,
                        keywords_ok,
                    )
                    if check is not None
                ]
                success = bool(answer.strip())
                passed = success and all(applicable_checks)
                error = None
                generation_path = answer_guard.get("generation_path")
                planning_path = (
                    result.get("planning_metadata") or {}
                ).get("generation_path")
                tool_step_count = int(result.get("tool_step_count") or 0)
            except Exception as exc:
                latency = time.perf_counter() - started
                answer = ""
                actual_tools = []
                actual_intent = "error"
                intent_ok = False if turn.get("expected_intent") else None
                expected_tools_ok = False
                allowed_tools_ok = False
                review_ok = False
                privacy_ok = False
                clarification_ok = False if turn.get("expected_intent") == "clarification" else None
                citations = []
                citations_ok = False if turn.get("require_citation") else None
                answer_guard_ok = False if turn.get("require_citation") else None
                memory_ok = False if turn.get("memory_has") else None
                keywords_ok = False
                success = False
                passed = False
                error = f"{type(exc).__name__}: {exc}"
                review_payload = None
                generation_path = "error"
                planning_path = "error"
                tool_step_count = 0

            rows.append(
                {
                    "id": case["id"],
                    "group": case["group"],
                    "turn_index": turn_index,
                    "question": turn["question"],
                    "success": success,
                    "passed": passed,
                    "actual_intent": actual_intent,
                    "expected_intent": turn.get("expected_intent"),
                    "intent_ok": intent_ok,
                    "actual_tools": actual_tools,
                    "expected_tools_ok": expected_tools_ok,
                    "allowed_tools_ok": allowed_tools_ok,
                    "review_ok": review_ok,
                    "privacy_ok": privacy_ok,
                    "clarification_ok": clarification_ok,
                    "citations": [
                        f"{doc_id}#{chunk_id}" for doc_id, chunk_id in citations
                    ],
                    "citations_ok": citations_ok,
                    "answer_guard_ok": answer_guard_ok,
                    "memory_ok": memory_ok,
                    "keywords_ok": keywords_ok,
                    "planning_path": planning_path,
                    "generation_path": generation_path,
                    "tool_step_count": tool_step_count,
                    "latency_seconds": latency,
                    "review_payload": review_payload,
                    "answer": answer,
                    "error": error,
                }
            )

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_contract": {
            "mode": "P2.1 Full Agentic mode with a real local Qwen service",
            "tool_protocol": "strict JSON planning with local Schema and allowlist validation",
            "latency_scope": "serial end-to-end graph turn, including review resume when required",
            "not_measured": [
                "industrial diagnosis accuracy",
                "human answer correctness",
                "concurrent throughput",
                "time to first token",
            ],
        },
        "service": {
            "base_url": args.base_url.rstrip("/"),
            "configured_model": args.model,
            "listed_models": model_ids,
        },
        "environment": _environment(),
        "inputs": {
            "case_count": len(cases),
            "planned_turn_count": planned_turns,
            "attempted_turn_count": len(rows),
            "eval_sha256": _sha256(args.eval_file),
            "chunks_sha256": _sha256(settings.rag_chunks_path),
            "agent_max_steps": settings.agent_max_steps,
        },
        "summary": _summarize(rows),
        "details": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")
    pass_rate = payload["summary"]["overall"]["case_pass_rate"]
    if args.min_case_pass_rate is not None and (
        pass_rate is None or pass_rate < args.min_case_pass_rate
    ):
        raise SystemExit(
            f"case_pass_rate {pass_rate} is below required {args.min_case_pass_rate}"
        )


if __name__ == "__main__":
    main()
