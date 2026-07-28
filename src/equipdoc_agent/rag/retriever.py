from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import Settings


def _tokenize(text: str) -> list[str]:
    try:
        import jieba

        tokens = [token.strip().lower() for token in jieba.lcut(text) if token.strip()]
    except ImportError:
        tokens = [
            token.lower()
            for token in re.findall(r"[\u4e00-\u9fff]{1,2}|[A-Za-z0-9_]+", text)
        ]
    return tokens


def _matches_filters(item: dict[str, Any], filters: dict[str, str] | None) -> bool:
    if not filters:
        return True
    metadata = item.get("metadata") or {}
    for key, expected in filters.items():
        if expected in {"", "general", None}:
            continue
        if str(metadata.get(key)) != str(expected):
            return False
    return True


def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


class KnowledgeRetriever:
    """Lazy, degradable retrieval layer.

    Lexical retrieval works with the base installation. Dense retrieval is added
    only when the optional RAG dependencies and a Chroma collection are present.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chunks = self._load_chunks(settings.rag_chunks_path)
        self.chunk_by_id = {item["chunk_id"]: item for item in self.chunks}
        self.tokenized = [_tokenize(item.get("text", "")) for item in self.chunks]
        self._bm25 = None
        self._dense_collection = None
        self._embedding_model = None
        self.warnings: list[str] = []
        self._init_bm25()
        self._init_dense_if_available()

    @staticmethod
    def _load_chunks(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def _init_bm25(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            self.warnings.append("rank-bm25 unavailable; using token-overlap retrieval")
            return
        self._bm25 = BM25Okapi(self.tokenized)

    def _init_dense_if_available(self) -> None:
        if not self.settings.rag_db_dir.exists():
            self.warnings.append("vector DB unavailable; dense retrieval disabled")
            return
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            client = chromadb.PersistentClient(path=str(self.settings.rag_db_dir))
            self._dense_collection = client.get_collection(self.settings.rag_collection)
            self._embedding_model = SentenceTransformer(
                self.settings.embedding_model,
                trust_remote_code=True,
            )
        except Exception as exc:
            self.warnings.append(f"dense retrieval disabled: {type(exc).__name__}")

    def _lexical_search(
        self,
        query: str,
        filters: dict[str, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        query_tokens = _tokenize(query)
        if self._bm25 is not None:
            scores = self._bm25.get_scores(query_tokens)
        else:
            query_set = set(query_tokens)
            scores = [
                len(query_set.intersection(tokens)) / max(1, len(query_set))
                for tokens in self.tokenized
            ]
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)
        hits = []
        for index, score in ranked:
            if float(score) <= 0:
                continue
            chunk = self.chunks[index]
            if not _matches_filters(chunk, filters):
                continue
            hits.append({**chunk, "lexical_score": float(score)})
            if len(hits) >= limit:
                break
        return hits

    def _dense_search(
        self,
        query: str,
        filters: dict[str, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self._dense_collection is None or self._embedding_model is None:
            return []
        embedding = self._embedding_model.encode([query], normalize_embeddings=True).tolist()[0]
        raw_filters = {
            key: value for key, value in (filters or {}).items() if value not in {None, "", "general"}
        }
        where = None
        if len(raw_filters) == 1:
            where = raw_filters
        elif len(raw_filters) > 1:
            where = {"$and": [{key: {"$eq": value}} for key, value in raw_filters.items()]}
        result = self._dense_collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=where,
            include=["distances"],
        )
        hits = []
        for chunk_id, distance in zip(
            result.get("ids", [[]])[0],
            result.get("distances", [[]])[0],
        ):
            chunk = self.chunk_by_id.get(chunk_id)
            if chunk:
                hits.append({**chunk, "dense_score": 1.0 / (1.0 + float(distance))})
        return hits

    def search(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        final_k = top_k or self.settings.rag_top_k
        pool_size = max(20, final_k)
        lexical = self._lexical_search(query, filters, pool_size)
        dense = self._dense_search(query, filters, pool_size)
        scores = _rrf(
            [
                [item["chunk_id"] for item in lexical],
                [item["chunk_id"] for item in dense],
            ]
        )
        merged: dict[str, dict[str, Any]] = {}
        for item in lexical + dense:
            chunk_id = item["chunk_id"]
            merged.setdefault(chunk_id, {}).update(item)
            merged[chunk_id]["rrf_score"] = scores.get(chunk_id, 0.0)
        return sorted(
            merged.values(),
            key=lambda item: item.get("rrf_score", 0.0),
            reverse=True,
        )[:final_k]

