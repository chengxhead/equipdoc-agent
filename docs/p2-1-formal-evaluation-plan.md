# P2.1 Agentic 正式评测计划与执行记录

> 状态：正式评测集已冻结，AutoDL 完整自动评测与失败分析已完成；人工复核工作簿已生成，当前 0/64 待复核。

## 1. 冻结评测集

正式输入为 [`data/eval/agentic_eval.jsonl`](../data/eval/agentic_eval.jsonl)，与 7-case Smoke 集完全分离，不复用原问题文本。

冻结版本 SHA-256：`7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8`。

| 分组 | Cases | Turns | 主要目标 |
|---|---:|---:|---|
| `knowledge_qa` | 10 | 10 | 轴承机理、信号特征、维修边界 |
| `cross_equipment` | 8 | 8 | 电机、管道、泵、齿轮箱、电池与 RAG 边界 |
| `signal_inspection` | 6 | 6 | 只读信号统计，不运行分类 |
| `clarification` | 6 | 6 | 缺少信号时主动澄清 |
| `safety_boundary` | 12 | 12 | 寿命、控制、阈值、跨工具、审批和信息编造边界 |
| `diagnosis` | 6 | 6 | 4 次 Approve、2 次 Reject 的单轮诊断审核 |
| `diagnosis_and_memory` | 8 | 16 | 诊断观察、知识追问和同线程结构化记忆 |
| **合计** | **56** | **64** | — |

评测集包含 38 个要求合法引用与 Answer Guard 的回合，以及 14 条包含诊断审核的端到端链路。真实运行和修复期间没有修改输入或标签，最终结果仍记录同一 SHA-256。

## 2. 自动判分合同

自动检查覆盖：

- 意图是否与预期一致；
- 预期工具是否实际执行；
- 实际工具是否保持在案例白名单内；
- Approve/Reject 审核门是否出现且载荷不暴露服务器路径；
- 缺少信号时是否返回明确澄清；
- 引用是否指向真实 `doc_id#chunk_id`；
- 最终答案是否通过 Grounded Answer Guard；
- 多轮结构化记忆是否保留；
- 最低限度必需关键词是否出现；
- 端到端延迟与工具步数。

自动 `case_pass_rate` 是结构化合同通过率，不是人工回答正确率。CNN 使用同一公开样例信号只验证工具链路，不构成工业诊断准确率测试。

## 3. 实际执行过程

执行遵循“先建立真实基线，再修复通用问题”的原则：

1. 服务探针与 2-case 预检通过；
2. 7 组分层预检 8/8 通过；
3. 首次完整运行不设置最低通过率，得到 57/64 的真实基线；
4. 保留失败 JSON，只修复通用路由、证据覆盖和现场复核证据选择问题；
5. 对失败子集定向回归，再完整复跑；
6. 最终使用 `--min-case-pass-rate 1.0` 验收，得到 64/64、退出码 0。

| 阶段 | Commit | 结果 | 失败 |
|---|---|---:|---|
| 首次完整基线 | `387e6f4` | 57/64 | 7 turns |
| 通用路由与证据覆盖修复后 | `82e9a5e` | 63/64 | `formal_014` |
| 最终完整验收 | `f34bc34` | 64/64 | 0 |

最终完整结果见 [`artifacts/p2_1/agentic_eval.json`](../artifacts/p2_1/agentic_eval.json)，全部中间证据和 SHA-256 见 [`artifacts/p2_1/README.md`](../artifacts/p2_1/README.md)。

## 4. 最终自动结果摘要

- 64/64 turn 自动合同通过；
- 意图、工具覆盖、白名单、审核、隐私、澄清、引用、Answer Guard、记忆和关键词指标均为 100%；
- 平均 / p50 / p95 端到端延迟为 7.472 / 8.541 / 16.758 秒；
- 52 个规划 turn 中 25 个模型计划被首轮或重试接受，27 个使用确定性 fallback；
- 38 个证据回答全部使用 `extractive_fallback`；
- 工具调用为知识检索 38 次、只读信号检查 6 次、轴承诊断 12 次。

自动 100% 不能解释为模型首轮规划、人工回答或工业诊断准确率 100%。

## 5. 人工复核计划

正式人工复核工作簿为 [`artifacts/p2_1/agentic_eval_human_review.xlsx`](../artifacts/p2_1/agentic_eval_human_review.xlsx)，已预填 64 个 turn，并用公式汇总复核进度和以下指标：

- 意图是否正确；
- 工具选择是否合理；
- 回答事实是否正确；
- 证据是否支持回答；
- 引用是否有用；
- 安全处理是否适当。

当前已复核 0/64。人工列未填写前，README、报告和简历中不得声称人工正确率、人工 groundedness、引用有用率或安全适当率。

建议至少由一名具备轴承振动与设备运维基础的复核人逐 turn 检查；对 0 分项记录原因，并把争议项交给第二名复核人复判。

## 6. 复现与校验

本地合同预检：

```powershell
.\.venv\Scripts\python.exe scripts\eval_agentic_full.py `
  --eval-file data\eval\agentic_eval.jsonl `
  --validate-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

AutoDL 完整运行：

```bash
python scripts/check_full_service.py \
  --timeout 120 \
  --output artifacts/p2_1/formal_service_check.json
python scripts/eval_agentic_full.py \
  --eval-file data/eval/agentic_eval.jsonl \
  --output artifacts/p2_1/agentic_eval.json \
  --min-case-pass-rate 1.0
```

更完整的结果、失败演进和解释边界见 [`p2-1-agentic-evaluation-report.md`](p2-1-agentic-evaluation-report.md)。
