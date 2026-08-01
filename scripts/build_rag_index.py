from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from equipdoc_agent.config import Settings
from equipdoc_agent.rag.index_manifest import (
    INDEX_MANIFEST_FILENAME,
    expected_index_manifest,
    read_index_manifest,
    write_index_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the optional EquipDoc Chroma index.")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env(ROOT)

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit('Install optional dependencies first: pip install -e ".[rag]"') from exc

    chunks = [
        json.loads(line)
        for line in settings.rag_chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    settings.rag_db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.rag_db_dir))
    expected_manifest = expected_index_manifest(settings, len(chunks))
    current_manifest = read_index_manifest(settings.rag_db_dir)
    rebuild = args.reset or current_manifest != expected_manifest
    if rebuild:
        manifest_path = settings.rag_db_dir / INDEX_MANIFEST_FILENAME
        manifest_path.unlink(missing_ok=True)
        try:
            client.delete_collection(settings.rag_collection)
        except Exception:
            pass
    collection = client.get_or_create_collection(settings.rag_collection)
    model = SentenceTransformer(settings.embedding_model, trust_remote_code=True)

    batch_size = 32
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        documents = [item["text"] for item in batch]
        embeddings = model.encode(documents, normalize_embeddings=True).tolist()
        metadata = []
        for item in batch:
            flattened = {}
            for key, value in (item.get("metadata") or {}).items():
                flattened[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
            flattened["doc_id"] = item.get("doc_id", "")
            metadata.append(flattened)
        collection.upsert(
            ids=[item["chunk_id"] for item in batch],
            documents=documents,
            metadatas=metadata,
            embeddings=embeddings,
        )

    indexed_count = int(collection.count())
    if indexed_count != len(chunks):
        raise SystemExit(
            f"Index contains {indexed_count} chunks, expected {len(chunks)}; rerun with --reset."
        )
    manifest_path = write_index_manifest(settings.rag_db_dir, expected_manifest)

    print(f"Built {len(chunks)} chunks in {settings.rag_db_dir}")
    print(f"Collection: {settings.rag_collection}")
    print(f"Embedding: {settings.embedding_model}")
    print(f"Manifest: {manifest_path.name}")


if __name__ == "__main__":
    main()
