# P2.1 Agentic 正式评测计划

> 状态：正式评测集已在真实运行前冻结；AutoDL 结果与人工复核尚未生成。

## 1. 评测集

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

与交接文档建议规模的对应关系：

- 单轮意图/工具：30 个案例；
- 安全与澄清：18 个案例；
- 多轮记忆：8 组；
- 包含诊断审核的端到端链路：14 条；
- 人工审核预期：12 次 Approve、2 次 Reject；
- 要求合法引用与 Answer Guard 的回合：38 个。

数据集 SHA-256 由 `--validate-only` 复核并随正式结果记录。若只修复代码，不修改评测标签或输入；只有确认存在标注错误时才允许修改数据集，并必须记录新哈希和变更原因。

## 2. 判分口径

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

自动 `case_pass_rate` 是结构化合同通过率，不是人工回答正确率。CNN 使用同一公开样例信号仅用于验证工具链路，也不构成工业诊断准确率测试。

## 3. 首次运行策略

第一次正式运行只建立真实基线，不设置 `--min-case-pass-rate`，避免为了追求 100% 而隐藏真实失败：

```bash
python scripts/eval_agentic_full.py \
  --eval-file data/eval/agentic_eval.jsonl \
  --output artifacts/p2_1/agentic_eval.json
```

运行后按以下类别整理失败：

1. 模型首轮规划失败；
2. 确定性规划 fallback；
3. 工具选择或审核失败；
4. 观察后决策失败；
5. 自然语言综合或引用校验失败；
6. 抽取式 fallback；
7. 自动关键词门槛假阴性；
8. 真正的任务失败或安全越界。

只有修复通用问题后才在同一冻结评测集上复跑。不得为某一道正式题增加硬编码分支。

## 4. 人工复核

正式运行完成后，基于原始 JSON 生成新的人工复核工作簿，至少评分：

- 意图是否正确；
- 工具选择是否合理；
- 回答事实是否正确；
- 证据是否支持回答；
- 引用是否有用；
- 安全处理是否适当。

人工列未填写前，README、报告和简历中不得声称人工正确率、人工 groundedness 或引用有用率。

## 5. 本地预检

```powershell
.\.venv\Scripts\python.exe scripts\eval_agentic_full.py `
  --eval-file data\eval\agentic_eval.jsonl `
  --validate-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

正式运行、人工复核和失败分析完成后，再更新 [`p2-1-agentic-evaluation-report.md`](p2-1-agentic-evaluation-report.md) 与项目 README。
