from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from equipdoc_agent.config import Settings
from equipdoc_agent.rag import KnowledgeRetriever


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _case_metrics(
    hits: list[dict[str, Any]], references: set[str], k_values: list[int]
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    ranked_docs = [str(hit.get("doc_id", "")) for hit in hits]
    for k in k_values:
        matched = set(ranked_docs[:k]).intersection(references)
        metrics[f"hit@{k}"] = float(bool(matched))
        metrics[f"recall@{k}"] = len(matched) / max(1, len(references))
    first_rank = next(
        (rank for rank, doc_id in enumerate(ranked_docs, start=1) if doc_id in references),
        None,
    )
    metrics[f"mrr@{max(k_values)}"] = 0.0 if first_rank is None else 1.0 / first_rank
    return metrics


def _summary(rows: list[dict[str, Any]], k_values: list[int]) -> dict[str, Any]:
    keys = [item for k in k_values for item in (f"hit@{k}", f"recall@{k}")]
    keys.append(f"mrr@{max(k_values)}")

    def summarize_group(items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "count": len(items),
            **{
                key: sum(row["metrics"][key] for row in items) / max(1, len(items))
                for key in keys
            },
        }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)
    return {
        "overall": summarize_group(rows),
        "by_group": {name: summarize_group(items) for name, items in sorted(grouped.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate public lexical RAG retrieval.")
    parser.add_argument("--eval-file", type=Path, default=ROOT / "data/eval/rag_eval100.jsonl")
    parser.add_argument("--chunks", type=Path, default=ROOT / "data/knowledge_chunks.jsonl")
    parser.add_argument("--k-values", default="1,3,5,10")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p1/rag_retrieval.json")
    parser.add_argument("--min-hit-at-5", type=float, default=None)
    parser.add_argument("--min-mrr-at-10", type=float, default=None)
    args = parser.parse_args()

    k_values = sorted({int(item) for item in args.k_values.split(",") if item.strip()})
    if not k_values or k_values[0] < 1:
        raise ValueError("k-values must contain positive integers")

    settings = Settings.from_env(ROOT)
    settings = replace(
        settings,
        rag_chunks_path=args.chunks.resolve(),
        rag_db_dir=(ROOT / "runtime/p1_no_vector_db").resolve(),
    )
    retriever = KnowledgeRetriever(settings)
    items = _load_jsonl(args.eval_file)
    rows = []
    for item in items:
        hits = retriever.search(
            str(item["question"]),
            filters=item.get("filters") or None,
            top_k=max(k_values),
        )
        references = {str(doc_id) for doc_id in item.get("reference_doc_ids", [])}
        rows.append(
            {
                "id": item["id"],
                "group": item["group"],
                "reference_doc_ids": sorted(references),
                "retrieved_doc_ids": [hit.get("doc_id") for hit in hits],
                "retrieved_chunk_ids": [hit.get("chunk_id") for hit in hits],
                "metrics": _case_metrics(hits, references, k_values),
            }
        )

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_contract": {
            "scope": "retrieval only; no answer generation or LLM judge",
            "relevance_level": "reference_doc_ids",
            "dense_retrieval": False,
            "lexical_backend": "bm25" if retriever._bm25 is not None else "token_overlap",
            "k_values": k_values,
            "warnings": retriever.warnings,
        },
        "inputs": {
            "eval_count": len(items),
            "eval_sha256": _sha256(args.eval_file),
            "chunks_sha256": _sha256(args.chunks),
        },
        "summary": _summary(rows, k_values),
        "details": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")
    overall = payload["summary"]["overall"]
    if args.min_hit_at_5 is not None:
        if "hit@5" not in overall:
            raise SystemExit("--min-hit-at-5 requires 5 in --k-values")
        if overall["hit@5"] < args.min_hit_at_5:
            raise SystemExit(
                f"hit@5 {overall['hit@5']:.4f} is below required {args.min_hit_at_5:.4f}"
            )
    if args.min_mrr_at_10 is not None:
        if "mrr@10" not in overall:
            raise SystemExit("--min-mrr-at-10 requires 10 as the largest --k-values entry")
        if overall["mrr@10"] < args.min_mrr_at_10:
            raise SystemExit(
                f"mrr@10 {overall['mrr@10']:.4f} is below required {args.min_mrr_at_10:.4f}"
            )


if __name__ == "__main__":
    main()
