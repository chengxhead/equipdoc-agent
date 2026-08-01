# P2.2 AutoDL 证据说明

本目录保存 2026-08-01 在 RTX 4090 + `qwen-equipdoc` Full Agentic 环境中产生的 P2.2 原始自动评测证据，以及本地生成的空白人工复核工作簿。

## 原始证据完整性

- 用户提供压缩包：`equipdoc-p2-2-evidence-20260801.tar.gz`
- 压缩包 SHA-256：`f0dc6352f9b8624246c48f97a501d43baef9ec3060493630937341f26c3a5543`
- 导入前检查：只包含 `artifacts/p2_2/` 下普通文件，无绝对路径、路径穿越或符号链接
- 清单校验：[`MANIFEST.sha256`](MANIFEST.sha256) 中 14 个原始文件全部匹配

`MANIFEST.sha256` 是 AutoDL 原始证据快照，不包含随后在本地生成的 `README.md` 和 `demo_human_review.xlsx`，因此不应修改它来追认本地文件。

## 文件索引

| 文件 | 用途 | 结果或状态 |
|---|---|---|
| [`source_bundle_sha256.txt`](source_bundle_sha256.txt) | AutoDL 使用的 P2.2 源码包哈希 | `3a90922b…` |
| [`service_check.json`](service_check.json) | 首次 Qwen 服务与 GPU 探针 | Ready |
| [`demo_precheck_before_fix.json`](demo_precheck_before_fix.json) | 两题整改前预检 | 1/2 |
| [`demo_precheck_fix1.json`](demo_precheck_fix1.json) | 第一轮证据覆盖修复 | 2/2，平均 11.497 秒 |
| [`demo_precheck_fix2.json`](demo_precheck_fix2.json) | 去除无效综合重试后预检 | 2/2，平均 7.179 秒 |
| [`demo_eval_run_1.json`](demo_eval_run_1.json) | 13-turn Demo 重复运行 1 | 13/13 |
| [`demo_eval_run_2.json`](demo_eval_run_2.json) | 13-turn Demo 重复运行 2 | 13/13 |
| [`demo_eval_run_3.json`](demo_eval_run_3.json) | 13-turn Demo 重复运行 3 | 13/13 |
| [`code_sha256.txt`](code_sha256.txt) | Fix 2 评测代码哈希 | 中间版本 |
| [`formal_service_check.json`](formal_service_check.json) | 正式回归前服务与 GPU 探针 | Ready，0.095 秒 |
| [`formal_regression_64_turn.json`](formal_regression_64_turn.json) | Fix 2 首次全量正式回归 | 61/64，保留 3 个真实失败 |
| [`formal_fix3_subset.json`](formal_fix3_subset.json) | Fix 3 的 4-turn 定向回归 | 4/4 |
| [`code_sha256_fix3.txt`](code_sha256_fix3.txt) | Fix 3 最终评测代码哈希 | 与本地最终对应文件一致 |
| [`formal_regression_64_turn_fix3.json`](formal_regression_64_turn_fix3.json) | Fix 3 最终 64-turn 正式回归 | 64/64 |
| [`demo_human_review.xlsx`](demo_human_review.xlsx) | Run 3 人工复核工作簿 | 0/13，人工字段保持空白 |

## 口径边界

- JSON 中 100% 表示固定自动合同在确定性策略、重试和 fallback 后通过，不是人工正确率；
- `structured_evidence_answer` 是经过槽位和引用约束的确定性回答路径，不证明模型自由综合稳定；
- 人工复核尚未开始，不能报告人工 groundedness、引用有用率或安全适当率；
- 本目录不包含模型权重、CNN 私有文件、`.env`、API Key 或 AutoDL 私有绝对路径；
- 详细分析、P2.1 对比和未解决项见 [`docs/p2-2-demo-quality-evaluation-report.md`](../../docs/p2-2-demo-quality-evaluation-report.md)。
