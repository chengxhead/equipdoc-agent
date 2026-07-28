# Migration notes from the AutoDL snapshot

## Preserved

- LangGraph review workflow;
- lightweight bearing CNN architecture;
- self-written maintenance knowledge notes;
- Agent/RAG evaluation inputs;
- deployment benchmark scripts and historical JSON;
- the original CWRU experiment scripts under `scripts/legacy/`.

## Replaced in P0

- AutoDL absolute paths with environment configuration;
- import-time model loading with lazy loading;
- raw server path input with sandboxed file upload;
- silent RAG failure with explicit health/degradation status;
- loose scripts with a `src/` package and `pyproject.toml`;
- missing-model crashes with a clearly labelled Demo mode.

## Deferred to P1

- cross-condition bearing evaluation;
- genuine structured LLM tool calling evaluation;
- authoritative RAG source metadata and human groundedness review;
- expanded tests for malformed, unsafe, multi-turn, and multi-tool cases;
- calibrated uncertainty and out-of-distribution rejection.

