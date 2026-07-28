from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from equipdoc_agent.agent import build_graph
from equipdoc_agent.config import Settings


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_REPORT_CLAIMS = ("剩余寿命为", "已经完成维修", "无需人工复核")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _interrupt_payload(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
    value = getattr(first, "value", first)
    return value if isinstance(value, dict) else None


def _last_content(result: dict) -> str:
    messages = result.get("messages", [])
    return str(getattr(messages[-1], "content", "")) if messages else ""


def _rate(items: list[dict[str, Any]], key: str) -> float | None:
    values = [bool(item[key]) for item in items if key in item and item[key] is not None]
    return None if not values else sum(values) / len(values)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)

    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "case_pass_rate": _rate(items, "passed"),
            "deterministic_route_accuracy": _rate(items, "route_ok"),
            "review_gate_coverage": _rate(items, "review_gate_ok"),
            "review_payload_privacy_rate": _rate(items, "privacy_ok"),
            "branch_compliance_rate": _rate(items, "branch_ok"),
            "knowledge_keyword_case_pass_rate": _rate(items, "knowledge_keywords_ok"),
        }

    return {
        "overall": block(rows),
        "by_group": {name: block(items) for name, items in sorted(grouped.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the public Demo Agent workflow.")
    parser.add_argument("--eval-file", type=Path, default=ROOT / "data/eval/agent_eval30.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p1/agent_workflow.json")
    parser.add_argument("--min-case-pass-rate", type=float, default=None)
    args = parser.parse_args()

    cases = json.loads(args.eval_file.read_text(encoding="utf-8"))
    settings = replace(Settings.from_env(ROOT), demo_mode=True)
    graph = build_graph(settings)
    sample_path = (settings.sample_root / "test_signal.npy").resolve()
    rows: list[dict[str, Any]] = []

    for case in cases:
        expected = case["expected"]
        expects_tool = bool(expected.get("should_call_tool"))
        config = {"configurable": {"thread_id": f"p1_{case['id']}_{uuid4().hex}"}}
        first = graph.invoke(
            {
                "messages": [HumanMessage(content=case["user_input"])],
                "signal_path": str(sample_path) if expects_tool else "",
            },
            config=config,
        )
        payload = _interrupt_payload(first)
        requested = (payload or {}).get("requested_tools") or []
        actual_tool = bool(payload)
        route_ok = actual_tool == expects_tool
        review_gate_ok = (not expects_tool) or bool(requested)
        tool_name_ok = (not expects_tool) or any(
            item.get("name") == expected.get("tool_name") for item in requested
        )
        serialized_payload = json.dumps(payload or {}, ensure_ascii=False)
        privacy_ok = (not expects_tool) or (
            "signal_path" not in serialized_payload
            and "test_signal.npy" in serialized_payload
            and str(settings.project_root) not in serialized_payload
        )

        branch_ok: bool | None = None
        knowledge_keywords_ok: bool | None = None
        final_content = _last_content(first)
        if case["group"] == "approve_branch" and payload:
            final = graph.invoke(Command(resume="approve"), config=config)
            final_content = _last_content(final)
            branch_ok = all(
                marker in final_content
                for marker in ("# 诊断报告", "Demo 提示", "## 检索证据", "## 已知边界")
            ) and not any(claim in final_content for claim in FORBIDDEN_REPORT_CLAIMS)
        elif case["group"] == "reject_branch" and payload:
            final = graph.invoke(Command(resume="reject"), config=config)
            final_content = _last_content(final)
            branch_ok = "取消" in final_content and "# 诊断报告" not in final_content
        elif case["group"] == "knowledge_only":
            keywords = expected.get("answer_keywords") or []
            knowledge_keywords_ok = bool(final_content.strip()) and all(
                keyword in final_content for keyword in keywords
            )

        checks = [route_ok, review_gate_ok, tool_name_ok, privacy_ok]
        if branch_ok is not None:
            checks.append(branch_ok)
        if knowledge_keywords_ok is not None:
            checks.append(knowledge_keywords_ok)
        rows.append(
            {
                "id": case["id"],
                "group": case["group"],
                "passed": all(checks),
                "route_ok": route_ok,
                "review_gate_ok": review_gate_ok,
                "tool_name_ok": tool_name_ok,
                "privacy_ok": privacy_ok,
                "branch_ok": branch_ok,
                "knowledge_keywords_ok": knowledge_keywords_ok,
                "review_payload": payload,
                "final_content": final_content,
            }
        )

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_contract": {
            "mode": "model-free Demo",
            "routing": "deterministic policy with an explicit safe signal fixture",
            "not_measured": ["LLM tool selection", "CNN classification accuracy", "answer groundedness"],
        },
        "inputs": {"eval_count": len(cases), "eval_sha256": _sha256(args.eval_file)},
        "summary": _summarize(rows),
        "details": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")
    actual_rate = payload["summary"]["overall"]["case_pass_rate"]
    if args.min_case_pass_rate is not None and actual_rate < args.min_case_pass_rate:
        raise SystemExit(
            f"case_pass_rate {actual_rate:.4f} is below required {args.min_case_pass_rate:.4f}"
        )


if __name__ == "__main__":
    main()
