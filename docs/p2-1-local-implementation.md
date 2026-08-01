# P2.1 Agentic 本地实现记录

> 状态：核心链路、本地回归、AutoDL 固定 Smoke 和 56-case / 64-turn 正式自动评测均已完成；正式人工复核为 0/64，仍待执行。

## 1. 已实现能力

- 严格 JSON 意图与计划 Prompt、一次格式重试和确定性 fallback；
- intent、工具名、参数、步骤数量、重复 ID、未知依赖和循环依赖校验；
- 删除模型输出中的 `signal_path`，真实文件路径只由系统从状态注入；
- 只读 `inspect_signal` 和结构化 `search_maintenance_knowledge`；
- `diagnose_bearing` 的 Approve/Reject 人工审核；
- 独立 `agentic_graph.py`，只在 Full + Agentic 显式开启时使用；
- 工具执行后让 Qwen 在剩余白名单工具、回答和澄清之间作出下一步决策；
- 同一 `thread_id` 保存文件名、诊断结果、搜索证据和待澄清问题；
- 上传新文件或明确更换文件时清理旧诊断状态；
- 工具直接输出与知识解释分开渲染；
- 对自然语言知识解释执行逐句引用、未知引用、完整证据覆盖、证据词汇、缩写、数字和越权表述校验；
- 草稿失败后重试一次，再失败返回抽取式证据原文；
- UI 不再在未上传新文件时用空字符串覆盖 checkpoint 中的旧路径。

## 2. 模式兼容

| 配置 | 实际路径 |
|---|---|
| `EQUIPDOC_DEMO_MODE=true` | 原无模型 Demo |
| `EQUIPDOC_DEMO_MODE=false` 且 `EQUIPDOC_AGENTIC_MODE=false` | 已发布 P2 baseline |
| `EQUIPDOC_DEMO_MODE=false` 且 `EQUIPDOC_AGENTIC_MODE=true` | P2.1 Agentic |

P2.1 使用严格 JSON 规划和本地工具执行，不是原生 Function Calling。安全沙箱、工具白名单、最大步数、高风险边界和诊断审批均由确定性代码控制，LLM 不能批准自己的计划。

## 3. 本地验证

最终代码基线 `f34bc34` 在本地与 AutoDL 均使用标准库 `unittest` 验收：

```bash
python -m unittest discover -s tests -q
python scripts/eval_agentic_full.py \
  --eval-file data/eval/agentic_eval.jsonl \
  --validate-only
```

结果：

- 93 项单元测试全部通过；
- 正式评测集 Schema 校验通过：56 cases、64 turns；
- 正式评测集 SHA-256 为 `7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8`；
- Demo、P2 baseline 与 P2.1 兼容路径均保留。

## 4. AutoDL 固定 Smoke

2026-07-31 在 RTX 4090 上运行固定 7 cases / 8 turns：

- 最终自动通过 8/8；
- 平均 / p50 / p95 端到端延迟 10.107 / 9.733 / 22.286 秒；
- 六个规划 turn 中两个首轮成功、四个确定性 fallback；
- 四个证据回答全部使用 `extractive_fallback`。

两类真实失败及修复过程已保留：知识问题被过度澄清，以及成功诊断观察被澄清覆盖。

## 5. AutoDL 正式自动评测

2026-07-31 至 2026-08-01 在同一 RTX 4090 环境运行冻结的 56 cases / 64 turns 正式集。

| 阶段 | Commit | 结果 | 说明 |
|---|---|---:|---|
| 首次完整基线 | `387e6f4` | 57/64 | 保留 7 个真实失败 |
| 通用修复后全量 | `82e9a5e` | 63/64 | 只剩 `formal_014` |
| 最终完整验收 | `f34bc34` | 64/64 | `--min-case-pass-rate 1.0`，退出码 0 |

最终自动指标：

- 意图、预期工具覆盖、白名单、审核、隐私、澄清、引用、Answer Guard、记忆和关键词指标均为 100%；
- 平均 / p50 / p95 延迟 7.472 / 8.541 / 16.758 秒；
- 52 个规划 turn 中 25 个模型计划被首轮或重试接受，27 个确定性 fallback；
- 38 个证据回答全部使用 `extractive_fallback`；
- 工具调用为知识检索 38 次、只读信号检查 6 次、轴承诊断 12 次。

完整报告见 [`p2-1-agentic-evaluation-report.md`](p2-1-agentic-evaluation-report.md)，原始证据和哈希见 [`../artifacts/p2_1/README.md`](../artifacts/p2_1/README.md)。

## 6. 尚未完成或不在本轮范围

- 正式人工回答正确性、证据支持性、引用有用性和安全适当性复核：当前 0/64；
- CNN 跨工况、按原始文件 Group Split 的工业诊断准确率；
- 多随机种子或多次重复运行的稳定性；
- 降低 51.9% 确定性规划 fallback；
- 提升自然语言证据综合通过率，减少证据回答 100% 抽取式 fallback。

不得把 P2 的 14/20、91.25% 或 0.433 秒 p95 写成 P2.1 指标，也不得把自动 64/64 写成人工正确率 100%。

## 7. AutoDL 复现

```bash
python -m unittest discover -s tests -q
python scripts/eval_agentic_full.py \
  --eval-file data/eval/agentic_eval.jsonl \
  --validate-only
python scripts/check_full_service.py \
  --timeout 120 \
  --output artifacts/p2_1/formal_service_check.json
python scripts/eval_agentic_full.py \
  --eval-file data/eval/agentic_eval.jsonl \
  --output artifacts/p2_1/agentic_eval.json \
  --min-case-pass-rate 1.0
```

运行前必须配置 Full Agentic 模式、Qwen OpenAI-compatible 服务、CNN 权重和归一化文件；模型权重、`.env`、虚拟环境、缓存与私有绝对路径不得提交仓库。
