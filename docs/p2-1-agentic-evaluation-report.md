# P2.1 Agentic 真实模型 Smoke 评估报告

> 状态：2026-07-31 已完成 AutoDL RTX 4090 真实 Qwen + CNN 的固定 Smoke Test；更大规模正式评测和人工正确性复核尚未完成。

## 1. 评估目标

本轮只验证 P2.1 受约束 Agentic 主链是否能够在真实模型环境中闭环运行，重点覆盖：

- 严格 JSON 意图识别与工具计划；
- 工具白名单、参数校验、步数上限和诊断审核门；
- `inspect_signal`、`diagnose_bearing`、`search_maintenance_knowledge` 三类工具；
- 工具观察后的继续检索、回答或澄清；
- 同一 `thread_id` 下的短期记忆；
- 逐句引用、证据词汇校验和抽取式安全降级；
- 剩余寿命与远程控制等高风险边界。

本报告不评估 CNN 的工业诊断准确率，也不把自动结构检查等同于人工回答正确率。

## 2. 运行环境

| 项目 | 实测值 |
|---|---|
| Git commit | `efc1c540e04c6b3b605455bd9fff9ac4ac360b4e` |
| GPU | NVIDIA GeForce RTX 4090，24564 MiB，驱动 580.105.08 |
| 操作系统 | Linux 5.15.0-78-generic x86_64，glibc 2.35 |
| Python | 3.12.3 |
| LangGraph | 1.2.6 |
| langchain-openai | 1.3.3 |
| NumPy | 2.3.2 |
| 服务模型名 | `qwen-equipdoc` |
| 服务地址 | `http://127.0.0.1:8001/v1` |
| 服务探针 | `READY`，0.543 秒 |
| 评测集 | `data/eval/agentic_smoke.jsonl`，7 cases / 8 turns |

完整环境记录见 [`artifacts/p2_1/service_check.json`](../artifacts/p2_1/service_check.json) 和 [`artifacts/p2_1/agentic_smoke.json`](../artifacts/p2_1/agentic_smoke.json)。

## 3. 最终自动结果

严格命令使用 `--min-case-pass-rate 1.0`，进程退出码为 0。

| 指标 | 结果 |
|---|---:|
| 执行成功率 | 100% |
| 固定 Smoke turn 自动通过率 | 100%（8/8） |
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
| 平均端到端延迟 | 10.107 秒 |
| p50 / p95 延迟 | 9.733 / 22.286 秒 |
| 平均工具步数 | 0.75 |

六个进入模型规划器的 turn 中，两个首轮规划成功，占 33.3%；四个使用确定性规划 fallback，占 66.7%。另外两个安全边界 turn 由本地安全策略直接处理。自动 `intent_accuracy=1.0` 包含 fallback 后的最终结果，不能解读为模型首轮意图识别率 100%。

四个需要知识证据回答的 turn 全部进入 `extractive_fallback`。这说明最终输出均能逐字回查，但也说明自然语言综合尚未稳定通过引用与术语校验。自动引用有效率 100% 反映的是受校验的最终输出，不代表模型自由生成内容全部可靠。

## 4. 分组覆盖

| 分组 | Turns | 自动结果 | 主要验证点 |
|---|---:|---:|---|
| `knowledge_qa` | 1 | 1/1 | 知识检索、引用与回答降级 |
| `cross_equipment` | 1 | 1/1 | 跨设备知识检索与证据约束 |
| `signal_inspection` | 1 | 1/1 | 只读信号统计工具 |
| `diagnosis_and_memory` | 2 | 2/2 | 诊断审核、观察保留、后续追问记忆 |
| `clarification` | 1 | 1/1 | 缺少信号时主动澄清 |
| `safety_boundary` | 2 | 2/2 | 剩余寿命与远程控制拒绝边界 |

## 5. 失败轨迹与修复证据

本轮保留了两类真实失败，而不是只发布最终成功结果。

| 阶段 | Commit / 结果 | 真实失败 | 修复 |
|---|---|---|---|
| 初始 2-case Smoke | `6ed1185`，0/2 | 两个自包含知识问题被过度判为 `clarification`，未调用检索工具 | `e04a2c0` 增加自包含问题约束、重试和确定性 fallback |
| 修复后 2-case Smoke | `af17605`，2/2 | 前两例恢复为知识检索并通过全部自动门 | 证据见 `smoke_2_after_overclarification_fix.json` |
| 修复前完整 Smoke | `af17605`，7/8 | `diagnose_bearing` 已成功，但观察被后续 `clarification` 隐藏 | `efc1c54` 保留成功工具观察，禁止纯澄清覆盖已完成结果 |
| 最终完整 Smoke | `efc1c54`，8/8 | 固定 Smoke 自动门全部通过 | 作为本报告最终基线 |

对应原始文件均保存在 [`artifacts/p2_1/`](../artifacts/p2_1/README.md)。

## 6. 人工复核状态

[`agentic_smoke_human_review.xlsx`](../artifacts/p2_1/agentic_smoke_human_review.xlsx) 已预填 8 个 turn 的问题、路由、工具、引用、答案和失败历史，并为以下维度提供 0/1 下拉评分：

- 意图是否正确；
- 工具选择是否正确；
- 回答是否正确；
- 证据是否支持回答；
- 引用是否有用；
- 安全处理是否适当。

当前已人工复核数量为 0/8，所有人工指标保持空白。因此本项目目前不声称人工回答正确率、人工 groundedness 或引用有用率。

## 7. 结论与边界

P2.1 的小规模真实模型 Smoke 里程碑已经完成：三种工具、诊断审核、观察后决策、短期记忆、主动澄清、引用约束和安全边界均形成可追溯闭环，且最终 8/8 自动门通过。

但以下工作仍未完成：

- 在已冻结的 56-case / 64-turn 正式 Agentic 评测集上完成 AutoDL 运行；
- 完成人工正确性、证据支持性和安全适当性复核；
- 降低 66.7% 的确定性规划 fallback 占比；
- 提升自然语言综合通过率，减少 100% 的证据回答抽取式 fallback；
- 通过跨工况、按原始文件分组的数据重新评估 CNN 工业诊断准确率；
- 进行多轮重复运行，评估延迟和生成稳定性。

因此，现阶段可以表述为“P2.1 真实模型固定 Smoke 自动检查 8/8 通过”，不能表述为“Agent 准确率 100%”“工业诊断准确率 100%”或“P2.1 正式评测已完成”。

## 8. 复现命令

```bash
python -m unittest discover -s tests -q
python scripts/eval_agentic_full.py --validate-only
python scripts/check_full_service.py \
  --timeout 120 \
  --output artifacts/p2_1/service_check.json
python scripts/eval_agentic_full.py \
  --output artifacts/p2_1/agentic_smoke.json \
  --min-case-pass-rate 1.0
```

运行前需要显式启用 Full Agentic 模式，并指向正在运行的 Qwen OpenAI-compatible 服务与本地 CNN 文件；模型权重、`.env` 和私有绝对路径不得提交仓库。
