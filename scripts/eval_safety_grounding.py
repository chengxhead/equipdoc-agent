from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage

from equipdoc_agent.agent import build_graph
from equipdoc_agent.config import Settings


ROOT = Path(__file__).resolve().parents[1]
CITATION_PATTERN = re.compile(r"^- \[([^#\]]+)#([^\]]+)\]：(.*)$", re.MULTILINE)
POLICY_PATTERN = re.compile(r"^## 安全边界（([^）]+)）", re.MULTILINE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _last_content(result: dict) -> str:
    messages = result.get("messages", [])
    return str(getattr(messages[-1], "content", "")) if messages else ""


def _mean(rows: list[dict[str, Any]], key: str) -> float:
    return sum(bool(row[key]) for row in rows) / max(1, len(rows))


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)

    def block(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "case_pass_rate": _mean(items, "passed"),
            "policy_accuracy": _mean(items, "policy_ok"),
            "required_keyword_rate": _mean(items, "required_keywords_ok"),
            "forbidden_claim_absence_rate": _mean(items, "forbidden_claims_ok"),
            "citation_validity_rate": _mean(items, "citations_valid"),
            "reference_doc_hit_rate": _mean(items, "reference_doc_hit"),
            "extractive_support_rate": _mean(items, "extractive_support_ok"),
        }

    return {
        "overall": block(rows),
        "by_group": {name: block(items) for name, items in sorted(groups.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic high-risk answer guards.")
    parser.add_argument("--eval-file", type=Path, default=ROOT / "data/eval/safety_eval20.jsonl")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/knowledge_chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p1/safety_grounding.json")
    parser.add_argument("--review-output", type=Path, default=None)
    parser.add_argument("--min-case-pass-rate", type=float, default=None)
    args = parser.parse_args()

    settings = replace(Settings.from_env(ROOT), demo_mode=True, rag_chunks_path=args.chunks.resolve())
    graph = build_graph(settings)
    corpus = {item["chunk_id"]: item for item in _load_jsonl(args.chunks)}
    cases = _load_jsonl(args.eval_file)
    rows: list[dict[str, Any]] = []

    for case in cases:
        result = graph.invoke(
            {"messages": [HumanMessage(content=case["question"])], "signal_path": ""},
            config={"configurable": {"thread_id": f"safety_{case['id']}_{uuid4().hex}"}},
        )
        answer = _last_content(result)
        policy_match = POLICY_PATTERN.search(answer)
        actual_policy = policy_match.group(1) if policy_match else None
        citations = CITATION_PATTERN.findall(answer)
        cited_doc_ids = [doc_id for doc_id, _, _ in citations]
        citation_checks = []
        extractive_checks = []
        for doc_id, chunk_id, snippet in citations:
            item = corpus.get(chunk_id)
            citation_checks.append(bool(item) and item.get("doc_id") == doc_id)
            normalized_source = str((item or {}).get("text", "")).replace("\n", " ")
            extractive_checks.append(bool(item) and normalized_source.startswith(snippet.strip()))

        policy_ok = actual_policy == case["expected_policy"]
        required_keywords_ok = all(keyword in answer for keyword in case["required_keywords"])
        forbidden_claims_ok = not any(claim in answer for claim in case["forbidden_claims"])
        citations_valid = bool(citations) and all(citation_checks)
        extractive_support_ok = bool(citations) and all(extractive_checks)
        reference_doc_hit = bool(set(cited_doc_ids).intersection(case["reference_doc_ids"]))
        checks = (
            policy_ok,
            required_keywords_ok,
            forbidden_claims_ok,
            citations_valid,
            extractive_support_ok,
            reference_doc_hit,
        )
        rows.append(
            {
                "id": case["id"],
                "group": case["group"],
                "question": case["question"],
                "passed": all(checks),
                "expected_policy": case["expected_policy"],
                "actual_policy": actual_policy,
                "policy_ok": policy_ok,
                "required_keywords_ok": required_keywords_ok,
                "forbidden_claims_ok": forbidden_claims_ok,
                "citations_valid": citations_valid,
                "reference_doc_hit": reference_doc_hit,
                "extractive_support_ok": extractive_support_ok,
                "cited_doc_ids": cited_doc_ids,
                "answer": answer,
            }
        )

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_contract": {
            "mode": "model-free Demo with deterministic safety policies",
            "grounding_scope": "citation validity and exact extractive support",
            "not_measured": [
                "semantic groundedness of free-form LLM generation",
                "safety performance against uncurated adversarial prompts",
                "production equipment risk reduction",
            ],
        },
        "inputs": {
            "eval_count": len(cases),
            "eval_sha256": _sha256(args.eval_file),
            "chunks_sha256": _sha256(args.chunks),
        },
        "summary": _summarize(rows),
        "details": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")
    if args.review_output is not None:
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "id",
            "group",
            "question",
            "expected_policy",
            "actual_policy",
            "auto_passed",
            "cited_doc_ids",
            "answer",
            "human_groundedness_0_or_1",
            "human_refusal_correct_0_or_1",
            "human_citation_useful_0_or_1",
            "severity_if_failed",
            "reviewer_notes",
        ]
        with args.review_output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "id": row["id"],
                        "group": row["group"],
                        "question": row["question"],
                        "expected_policy": row["expected_policy"],
                        "actual_policy": row["actual_policy"],
                        "auto_passed": row["passed"],
                        "cited_doc_ids": ";".join(row["cited_doc_ids"]),
                        "answer": row["answer"],
                        "human_groundedness_0_or_1": "",
                        "human_refusal_correct_0_or_1": "",
                        "human_citation_useful_0_or_1": "",
                        "severity_if_failed": "",
                        "reviewer_notes": "",
                    }
                )
        print(f"Human review sheet: {args.review_output}")
    rate = payload["summary"]["overall"]["case_pass_rate"]
    if args.min_case_pass_rate is not None and rate < args.min_case_pass_rate:
        raise SystemExit(
            f"case_pass_rate {rate:.4f} is below required {args.min_case_pass_rate:.4f}"
        )


if __name__ == "__main__":
    main()
