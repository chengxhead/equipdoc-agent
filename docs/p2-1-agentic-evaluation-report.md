# P2.1 Agentic 真实模型评估报告

> 状态：截至 2026-08-01，AutoDL RTX 4090 上的固定 Smoke 与 56-case / 64-turn 正式自动评测均已完成；正式人工正确性复核工作簿已生成，但当前仍为 0/64。

## 1. 评估目标与边界

本轮验证 P2.1 受约束 Agentic 主链能否在真实 Qwen + CNN 环境中闭环运行，重点覆盖：

- 严格 JSON 意图识别与工具计划；
- 工具白名单、参数校验、步数上限和诊断审核门；
- `inspect_signal`、`diagnose_bearing`、`search_maintenance_knowledge` 三类工具；
- 工具观察后的继续检索、回答或澄清；
- 同一 `thread_id` 下的结构化短期记忆；
- 逐句引用、证据覆盖、术语校验和抽取式安全降级；
- 剩余寿命、远程控制、跨设备误用和信息编造等安全边界。

自动 `case_pass_rate` 是固定评测合同的结构化通过率。本报告不评估 CNN 工业诊断准确率，也不把自动通过率等同于人工回答正确率。

## 2. 运行环境与冻结输入

| 项目 | 实测值 |
|---|---|
| 最终 Git commit | `f34bc340401029cf5ca510fe76641f4a8d59a6cb` |
| GPU | NVIDIA GeForce RTX 4090，24564 MiB，驱动 580.105.08 |
| 操作系统 | Linux 5.15.0-78-generic x86_64，glibc 2.35 |
| Python | 3.12.3 |
| LangGraph | 1.2.6 |
| langchain-openai | 1.3.3 |
| NumPy | 2.3.2 |
| 服务模型名 | `qwen-equipdoc` |
| 服务地址 | `http://127.0.0.1:8001/v1` |
| 正式服务探针 | `READY`，0.112 秒 |
| Smoke 输入 | `data/eval/agentic_smoke.jsonl`，7 cases / 8 turns |
| 正式输入 | `data/eval/agentic_eval.jsonl`，56 cases / 64 turns |
| 正式输入 SHA-256 | `7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8` |

正式环境记录见 [`formal_service_check.json`](../artifacts/p2_1/formal_service_check.json)，最终结果见 [`agentic_eval.json`](../artifacts/p2_1/agentic_eval.json)。固定 Smoke 结果继续保留在 [`agentic_smoke.json`](../artifacts/p2_1/agentic_smoke.json)。

## 3. 最终正式自动结果

最终完整命令使用 `--min-case-pass-rate 1.0`，进程退出码为 0。

| 指标 | 结果 |
|---|---:|
| 执行成功率 | 100% |
| 正式 turn 自动通过率 | 100%（64/64） |
| 意图一致率 | 100% |
| 预期工具覆盖率 | 100% |
| 工具白名单合规率 | 100% |
| 审核门合规率 | 100% |
| 审核载荷隐私率 | 100% |
| 主动澄清合规率 | 100% |
| 引用有效率 | 100% |
| Grounded Answer Guard 通过率 | 100% |
| 多轮记忆保持率 | 100% |
| 必需关键词 case 通过率 | 100% |
| 平均端到端延迟 | 7.472 秒 |
| p50 / p95 延迟 | 8.541 / 16.758 秒 |
| 平均工具步数 | 0.875 |

这些自动指标包含确定性策略、fallback 和抽取式答案的最终结果，不能解释为“模型首轮规划准确率 100%”或“自然语言回答准确率 100%”。

## 4. 规划、生成与工具分布

### 4.1 规划路径

64 个 turn 中，52 个进入模型规划器，12 个由本地安全策略直接处理。

| 规划路径 | Turns | 占规划 turn |
|---|---:|---:|
| `first_pass` | 20 | 38.5% |
| `retry` | 5 | 9.6% |
| `deterministic_fallback` | 27 | 51.9% |
| **模型计划被首轮或重试接受** | **25** | **48.1%** |

自动 `intent_accuracy=1.0` 统计的是重试和确定性 fallback 后的最终结果；模型计划实际被接受的比例为 48.1%。

### 4.2 回答生成路径

| 生成路径 | Turns | 说明 |
|---|---:|---|
| `extractive_fallback` | 38 | 需要知识证据的回答全部走受校验的抽取式原文 |
| `tool_observation_only` | 6 | 只返回确定性工具观察 |
| 无生成路径 | 20 | 澄清、安全边界或本地策略直接回答 |

38 个需要证据回答的 turn 全部使用 `extractive_fallback`。因此自动引用有效率 100% 说明最终证据可以逐字回查，但同时暴露自然语言证据综合尚未稳定通过校验。

### 4.3 工具调用

| 工具 | 调用次数 | 权限边界 |
|---|---:|---|
| `search_maintenance_knowledge` | 38 | 只读，可直接执行 |
| `inspect_signal` | 6 | 只读，可直接执行 |
| `diagnose_bearing` | 12 | 必须经过 Approve/Reject |

## 5. 分组覆盖

| 分组 | Turns | 自动结果 | 主要验证点 |
|---|---:|---:|---|
| `knowledge_qa` | 10 | 10/10 | 知识检索、完整证据覆盖与引用 |
| `cross_equipment` | 8 | 8/8 | 电机、管道、泵、齿轮箱、电池与 RAG 边界 |
| `signal_inspection` | 6 | 6/6 | 只读信号统计，不运行分类 |
| `clarification` | 6 | 6/6 | 缺少信号或关键信息时主动澄清 |
| `safety_boundary` | 12 | 12/12 | 寿命、控制、审批和信息编造边界 |
| `diagnosis` | 6 | 6/6 | 单轮诊断审核、Approve/Reject |
| `diagnosis_and_memory` | 16 | 16/16 | 诊断观察、知识追问和同线程记忆 |

## 6. 正式失败演进

正式集在真实运行前冻结，整个修复过程没有修改输入或标签，SHA-256 始终保持不变。

| 阶段 | Commit | 自动结果 | 失败 | 平均 / p95 延迟 |
|---|---|---:|---|---:|
| 首次完整真实基线 | `387e6f4` | 57/64（89.1%） | 7 turns：证据覆盖、意图路由、工具链路和多轮关键词问题 | 11.532 / 25.264 秒 |
| 通用路由与证据覆盖修复后 | `82e9a5e` | 63/64（98.4%） | 仅 `formal_014` 现场复核证据聚焦失败 | 7.078 / 16.858 秒 |
| 聚焦现场复核证据后 | `f34bc34` | 64/64（100%） | 0 | 7.472 / 16.758 秒 |

关键修复均为通用规则：

- 避免自包含知识问题被过度澄清；
- 保护成功工具观察，禁止后续纯澄清覆盖结果；
- 强化诊断、信号检查与知识问答的通用意图路由；
- 要求多子问题相关证据完整覆盖；
- 对高风险现场复核请求优先选择安全隔离、压力/流量/声振与人工巡检证据。

基线、定向回归、修复前全量与最终全量 JSON 均保存在 [`artifacts/p2_1/`](../artifacts/p2_1/README.md)，没有只保留最终成功结果。

## 7. Smoke 里程碑

正式评测前的固定 Smoke 仍作为工程演进证据保留：最终 `efc1c54` 上 8/8 自动通过，平均 / p95 延迟为 10.107 / 22.286 秒。六个进入规划器的 turn 中两个首轮成功、四个确定性 fallback；四个证据回答全部为 `extractive_fallback`。

Smoke 阶段保留了两类真实失败：知识问题被过度澄清，以及成功诊断观察被后续澄清覆盖。对应原始文件见 [`artifacts/p2_1/README.md`](../artifacts/p2_1/README.md)。

## 8. 人工复核状态

[`agentic_eval_human_review.xlsx`](../artifacts/p2_1/agentic_eval_human_review.xlsx) 已预填全部 64 个 turn 的问题、路由、工具、引用、答案、失败演进和运行环境，并提供以下 0/1 人工评分：

- 意图是否正确；
- 工具选择是否合理；
- 回答事实是否正确；
- 证据是否支持回答；
- 引用是否有用；
- 安全处理是否适当。

当前正式人工复核为 0/64，所有人工指标保持空白。因此目前不能声称人工回答正确率、人工 groundedness、引用有用率或安全适当率。

## 9. 结论与下一步

P2.1 的工程实现与正式自动验收已经完成：三种工具、诊断审核、观察后决策、短期记忆、主动澄清、引用约束和安全边界在冻结正式集上形成可追溯闭环，最终 64/64 自动合同通过。

仍需完成或继续优化：

1. 完成 64 个 turn 的人工质量复核；
2. 降低 51.9% 的确定性规划 fallback 占比；
3. 提升自然语言证据综合通过率，减少证据回答 100% 抽取式 fallback；
4. 进行多随机种子或多轮重复运行，评估稳定性与延迟波动；
5. 通过跨工况、按原始文件分组的数据重新评估 CNN 工业诊断准确率。

当前可以表述为“冻结的 56-case / 64-turn P2.1 正式自动评测 64/64 通过”，不能表述为“Agent 人工准确率 100%”“groundedness 100%”或“工业诊断准确率 100%”。

## 10. 复现命令

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

运行前需要显式启用 Full Agentic 模式，并指向正在运行的 Qwen OpenAI-compatible 服务与本地 CNN 文件；模型权重、`.env` 和私有绝对路径不得提交仓库。
