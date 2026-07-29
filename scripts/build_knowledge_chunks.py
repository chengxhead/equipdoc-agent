from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _parse_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"Missing frontmatter in {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError(f"Unclosed frontmatter in {path}") from exc

    metadata: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid frontmatter line in {path}: {line}")
        clean_value = value.strip()
        metadata[key.strip()] = (
            [item.strip() for item in clean_value.split(",") if item.strip()]
            if key.strip() == "keywords"
            else clean_value
        )
    return metadata, "\n".join(lines[end + 1 :]).strip()


def _sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    active_path = "正文"
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            sections.append((active_path, text))
        buffer.clear()

    for line in markdown.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        heading = match.group(2).strip()
        del heading_stack[level - 1 :]
        while len(heading_stack) < level - 1:
            heading_stack.append("未命名章节")
        heading_stack.append(heading)
        active_path = " > ".join(heading_stack)
    flush()
    return sections


def build_chunks(knowledge_dir: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()
    for path in sorted(knowledge_dir.glob("*.md")):
        metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"), path)
        doc_id = str(metadata.get("doc_id", "")).strip()
        title = str(metadata.get("title", "")).strip()
        if not doc_id or not title:
            raise ValueError(f"doc_id and title are required in {path}")
        if doc_id in seen_doc_ids:
            raise ValueError(f"Duplicate doc_id: {doc_id}")
        seen_doc_ids.add(doc_id)
        source_path = path.relative_to(ROOT).as_posix()
        for index, (heading_path, text) in enumerate(_sections(body), start=1):
            chunk_id = f"{doc_id}_c{index:03d}"
            chunk_metadata = {
                **metadata,
                "source_path": source_path,
                "heading_path": heading_path,
                "chunk_id": chunk_id,
                "char_count": len(text),
            }
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "title": title,
                    "heading_path": heading_path,
                    "text": text,
                    "metadata": chunk_metadata,
                }
            )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic lexical knowledge chunks.")
    parser.add_argument("--knowledge-dir", type=Path, default=ROOT / "data/knowledge")
    parser.add_argument("--output", type=Path, default=ROOT / "data/knowledge_chunks.jsonl")
    parser.add_argument("--check", action="store_true", help="Fail if output is not up to date.")
    args = parser.parse_args()

    chunks = build_chunks(args.knowledge_dir.resolve())
    payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in chunks) + "\n"
    doc_count = len({item["doc_id"] for item in chunks})
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != payload:
            raise SystemExit(
                f"Knowledge chunks are stale: run {Path(__file__).name} and commit the output."
            )
        print(f"Verified {len(chunks)} chunks from {doc_count} documents: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    print(f"Built {len(chunks)} chunks from {doc_count} documents: {args.output}")


if __name__ == "__main__":
    main()
