from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..config import Settings


INDEX_MANIFEST_FILENAME = "equipdoc_index_manifest.json"
INDEX_MANIFEST_SCHEMA = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_index_manifest(settings: Settings, chunk_count: int) -> dict[str, Any]:
    return {
        "schema_version": INDEX_MANIFEST_SCHEMA,
        "chunks_sha256": _sha256(settings.rag_chunks_path),
        "chunk_count": int(chunk_count),
        "collection": settings.rag_collection,
        "embedding_model": settings.embedding_model,
    }


def read_index_manifest(directory: Path) -> dict[str, Any] | None:
    path = directory / INDEX_MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_index_manifest(directory: Path, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / INDEX_MANIFEST_FILENAME
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination
