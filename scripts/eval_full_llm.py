from __future__ import annotations

import argparse
import csv
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

from equipdoc_agent.agent import build_graph
from equipdoc_agent.agent.knowledge_answer import extract_citations
from equipdoc_agent.config import Settings
from equipdoc_agent.rag import KnowledgeRetriever


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


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


def _last_message(result: dict):
    messages = result.get("messages", [])
    return messages[-1] if messages else None


def _usage(message) -> dict[str, Any]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage
    metadata = getattr(message, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    return token_usage if isinstance(token_usage, dict) else {}


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)

    def rate(items: list[dict[str, Any]], key: str) -> float:
        return sum(bool(item.get(key)) for item in items) / max(1, len(items))

    def mean(items: list[dict[str, Any]], key: str) -> float | None:
        values = [item[key] for item in items if item.get(key) is not None]
        return statistics.mean(values) if values else None

    latencies = [row["latency_seconds"] for row in rows if row.get("success")]

    def quality_block(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            "success_rate": rate(items, "success"),
            "llm_invocation_rate": rate(items, "llm_called"),
            "case_pass_rate": rate(items, "passed"),
            "average_keyword_recall": mean(items, "keyword_recall"),
            "forbidden_claim_absence_rate": rate(items, "forbidden_claims_ok"),
            "citation_validity_rate": rate(items, "citations_valid"),
            "reference_doc_hit_rate": rate(items, "reference_doc_hit"),
        }

    return {
        "overall": {
            **quality_block(rows),
            "latency_mean_seconds": statistics.mean(latencies) if latencies else None,
            "latency_p50_seconds": _percentile(latencies, 50),
            "latency_p95_seconds": _percentile(latencies, 95),
            "average_output_characters": mean(rows, "output_characters"),
            "average_output_tokens": mean(rows, "output_tokens"),
        },
        "by_group": {
            name: quality_block(items) for name, items in sorted(groups.items())
        },
    }


def main() -> None:
    base_settings = Settings.from_env(ROOT)
    parser = argparse.ArgumentParser(description="Evaluate real Full-mode Qwen RAG answers.")
    parser.add_argument("--eval-file", type=Path, default=ROOT / "data/eval/full_llm_eval20.jsonl")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/knowledge_chunks.jsonl")
    parser.add_argument("--base-url", default=base_settings.llm_base_url)
    parser.add_argument("--model", default=base_settings.llm_model)
    parser.add_argument("--api-key", default=base_settings.llm_api_key)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--skip-warmup", action="store_true")
    parser.add_argument("--use-configured-vector-db", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p2/full_llm_eval.json")
    parser.add_argument("--review-output", type=Path, default=None)
    parser.add_argument("--max-consecutive-errors", type=int, default=3)
    args = parser.parse_args()

    model_ids = _service_models(args.base_url, args.api_key, args.timeout)
    if args.model not in model_ids:
        raise SystemExit(f"Configured model {args.model!r} is not listed by service: {model_ids}")
    rag_db_dir = (
        base_settings.rag_db_dir
        if args.use_configured_vector_db
        else (ROOT / "runtime/p2_no_vector_db").resolve()
    )
    settings = replace(
        base_settings,
        demo_mode=False,
        llm_base_url=args.base_url.rstrip("/"),
        llm_model=args.model,
        llm_api_key=args.api_key,
        llm_timeout_seconds=args.timeout,
        rag_chunks_path=args.chunks.resolve(),
        rag_db_dir=rag_db_dir,
    )
    retriever_probe = KnowledgeRetriever(settings)
    retrieval = {
        "dense_enabled": retriever_probe._dense_collection is not None,
        "lexical_backend": "bm25" if retriever_probe._bm25 is not None else "token_overlap",
        "warnings": retriever_probe.warnings,
    }
    graph = build_graph(settings)
    corpus = {item["chunk_id"]: item for item in _load_jsonl(args.chunks)}
    cases = _load_jsonl(args.eval_file)
    if args.limit > 0:
        cases = cases[: args.limit]

    if not args.skip_warmup and cases:
        print("Warmup request...", flush=True)
        graph.invoke(
            {"messages": [HumanMessage(content=cases[0]["question"])], "signal_path": ""},
            config={"configurable": {"thread_id": f"p2_warmup_{uuid4().hex}"}},
        )

    rows: list[dict[str, Any]] = []
    consecutive_errors = 0
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        started = time.perf_counter()
        try:
            result = graph.invoke(
                {"messages": [HumanMessage(content=case["question"])], "signal_path": ""},
                config={"configurable": {"thread_id": f"p2_{case['id']}_{uuid4().hex}"}},
            )
            latency = time.perf_counter() - started
            message = _last_message(result)
            answer = str(getattr(message, "content", ""))
            usage = _usage(message)
            response_metadata = getattr(message, "response_metadata", None) or {}
            llm_called = bool(usage) or bool(
                response_metadata.get("model_name")
                or response_metadata.get("model")
                or response_metadata.get("token_usage")
            )
            citations = extract_citations(answer)
            citation_checks = [
                chunk_id in corpus and corpus[chunk_id].get("doc_id") == doc_id
                for doc_id, chunk_id in citations
            ]
            keyword_hits = [keyword in answer for keyword in case["required_keywords"]]
            keyword_recall = sum(keyword_hits) / max(1, len(keyword_hits))
            forbidden_claims_ok = not any(
                claim in answer for claim in case.get("forbidden_claims", [])
            )
            citations_valid = bool(citations) and all(citation_checks)
            reference_doc_hit = bool(
                {doc_id for doc_id, _ in citations}.intersection(case["reference_doc_ids"])
            )
            success = bool(answer.strip())
            passed = (
                success
                and llm_called
                and keyword_recall >= 0.5
                and forbidden_claims_ok
                and citations_valid
                and reference_doc_hit
            )
            error = None
            consecutive_errors = 0
        except Exception as exc:
            latency = time.perf_counter() - started
            answer = ""
            usage = {}
            citations = []
            keyword_recall = 0.0
            forbidden_claims_ok = False
            citations_valid = False
            reference_doc_hit = False
            success = False
            llm_called = False
            passed = False
            error = f"{type(exc).__name__}: {exc}"
            consecutive_errors += 1
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        rows.append(
            {
                "id": case["id"],
                "group": case["group"],
                "success": success,
                "llm_called": llm_called,
                "passed": passed,
                "keyword_recall": keyword_recall,
                "forbidden_claims_ok": forbidden_claims_ok,
                "citations_valid": citations_valid,
                "reference_doc_hit": reference_doc_hit,
                "citations": [f"{doc_id}#{chunk_id}" for doc_id, chunk_id in citations],
                "latency_seconds": latency,
                "output_characters": len(answer),
                "output_tokens": output_tokens,
                "usage": usage,
                "answer": answer,
                "error": error,
            }
        )
        if consecutive_errors >= args.max_consecutive_errors:
            print(
                f"Stopping after {consecutive_errors} consecutive service errors.",
                flush=True,
            )
            break

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_contract": {
            "mode": "Full mode with a real OpenAI-compatible local Qwen service",
            "quality_gate": "keyword recall >= 0.5, valid citation, reference hit, no listed forbidden claim",
            "latency_scope": "serial end-to-end graph invocation after one warmup",
            "not_measured": [
                "concurrent throughput",
                "time to first token",
                "human semantic groundedness",
                "CNN classification accuracy",
            ],
        },
        "service": {
            "base_url": args.base_url.rstrip("/"),
            "configured_model": args.model,
            "listed_models": model_ids,
        },
        "retrieval": retrieval,
        "environment": _environment(),
        "inputs": {
            "planned_eval_count": len(cases),
            "attempted_eval_count": len(rows),
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
        fields = [
            "id",
            "group",
            "answer",
            "auto_passed",
            "keyword_recall",
            "citations",
            "human_groundedness_0_or_1",
            "human_answer_correct_0_or_1",
            "human_citation_useful_0_or_1",
            "reviewer_notes",
        ]
        with args.review_output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "id": row["id"],
                        "group": row["group"],
                        "answer": row["answer"],
                        "auto_passed": row["passed"],
                        "keyword_recall": row["keyword_recall"],
                        "citations": ";".join(row["citations"]),
                        "human_groundedness_0_or_1": "",
                        "human_answer_correct_0_or_1": "",
                        "human_citation_useful_0_or_1": "",
                        "reviewer_notes": "",
                    }
                )
        print(f"Human review sheet: {args.review_output}")


if __name__ == "__main__":
    main()
