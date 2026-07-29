# Data layout

- `samples/`: small files required for the safe Demo mode.
- `knowledge/`: self-written project notes. They require authoritative source metadata in P1.
- `knowledge_chunks.jsonl`: pre-built chunks so lexical retrieval works without a vector database.

After editing `data/knowledge/*.md`, rebuild and verify the committed chunks:

```bash
python scripts/build_knowledge_chunks.py
python scripts/build_knowledge_chunks.py --check
```
- `eval/`: original Agent and RAG evaluation inputs.
- `raw/` and `processed/`: generated locally and ignored by Git.

Do not add employer data, real equipment identifiers, internal manuals, or confidential operating parameters.
