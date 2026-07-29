# P2 Full-mode evidence

This directory contains the sanitized outputs from the 2026-07-29 AutoDL Full-mode run on commit `3226c70d57214865bfe99c160c646192caffeef6`.

## Current evidence

- `service_check.json`: RTX 4090 service preflight; `ready=true`.
- `full_llm_eval.json`: 20-case machine-readable result and complete answers.
- `full_llm_human_review.csv`: 20-row review sheet; human 0/1 fields intentionally remain blank.
- `smoke_initial_failure.json`: initial real-model failure with no valid citations.
- `smoke_v6_safe_2_of_3.json`: final 3-case smoke before the 20-case run.

The strict 20-case automatic pass rate is 70% (14/20), average required-keyword recall is 91.25%, exact cited-evidence match is 100%, and serial p95 latency after warmup is 0.433 seconds. These are automatic pipeline metrics, not human answer accuracy or industrial diagnosis accuracy.

See [`../../docs/p2-full-evaluation-report.md`](../../docs/p2-full-evaluation-report.md) for definitions, failure analysis, and limitations.

Do not commit model weights, API keys, raw private data, vector databases, caches, or absolute-path inventories.
