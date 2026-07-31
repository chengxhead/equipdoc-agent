# P2.1 Agentic 本地实现记录

> 状态：核心链路、本地回归和 AutoDL 真实 Qwen + CNN 固定 Smoke Test 已完成；更大规模正式评测与人工复核尚未完成。

## 本轮实现

- 新增严格 JSON 意图与计划 Prompt、一次格式重试和确定性 fallback；
- 校验 intent、工具名、参数、步骤数量、重复 ID、未知依赖和循环依赖；
- 删除模型输出中的 `signal_path`，真实文件路径只由系统从状态注入；
- 新增只读 `inspect_signal` 和结构化 `search_maintenance_knowledge`；
- 保留 `diagnose_bearing` 的 Approve/Reject 人工审核；
- 新建独立 `agentic_graph.py`，只在 Full + Agentic 显式开启时使用；
- 工具执行后让 Qwen 在剩余白名单工具、回答和澄清之间作出下一步决策；
- 使用同一 `thread_id` 保存文件名、诊断结果、搜索证据和待澄清问题；
- 上传新文件或明确要求更换文件时清理旧诊断状态；
- 将工具直接输出与知识解释分开渲染；
- 对自然语言知识解释执行逐句引用、未知引用、证据词汇、缩写、数字和越权表述校验；
- 自然语言草稿失败后重试一次，再失败返回抽取式证据原文；
- UI 不再在未上传新文件时用空字符串覆盖 checkpoint 中的旧路径。

## 模式兼容

| 配置 | 实际路径 |
|---|---|
| `EQUIPDOC_DEMO_MODE=true` | 原无模型 Demo |
| `EQUIPDOC_DEMO_MODE=false` 且 `EQUIPDOC_AGENTIC_MODE=false` | 已发布 P2 baseline |
| `EQUIPDOC_DEMO_MODE=false` 且 `EQUIPDOC_AGENTIC_MODE=true` | P2.1 Agentic |

P2.1 使用严格 JSON 规划和本地工具执行，不是原生 Function Calling。

## 本地验证

2026-07-31 在 Windows PowerShell 执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m equipdoc_agent.health --strict
.\.venv\Scripts\python.exe scripts\demo_smoke.py
.\.venv\Scripts\python.exe scripts\eval_agentic_full.py --validate-only
```

结果：

- 90 项单元测试全部通过；
- Demo 严格健康检查通过；
- Demo Smoke Test 通过；
- Agentic Smoke 数据集 Schema 校验通过：7 个案例、8 个回合；
- 当前虚拟环境未安装可选开发依赖 `pytest` 和 `ruff`，因此验收使用标准库 `unittest`、`compileall` 和 `git diff --check`。

## AutoDL 真实 Smoke 验证

2026-07-31 在 RTX 4090 上运行 `data/eval/agentic_smoke.jsonl`，固定 7 个案例、8 个回合的最终自动结果为：

- 严格自动通过率 8/8；
- 意图、预期工具覆盖、工具白名单、审核门、审核载荷隐私、主动澄清、引用有效性、Grounded Answer Guard 和多轮记忆指标均为 100%；
- 平均 / p50 / p95 端到端延迟为 10.107 / 9.733 / 22.286 秒；
- 6 个进入规划器的 turn 中，2 个首轮规划成功，4 个使用确定性 fallback；
- 4 个需要证据回答的 turn 全部使用 `extractive_fallback`。

两类真实失败及修复过程也已保留：知识问题被过度澄清，以及成功诊断观察被澄清覆盖。最终报告见 [`p2-1-agentic-evaluation-report.md`](p2-1-agentic-evaluation-report.md)，原始证据见 [`../artifacts/p2_1/README.md`](../artifacts/p2_1/README.md)。

## 仍未验证

- 已冻结 56-case / 64-turn 正式 Agentic 评测集，但尚未在 AutoDL 运行；
- 人工回答正确性、证据支持性和引用有用性；
- CNN 工业诊断准确率。

不得把 P2 的 14/20、91.25% 或 0.433 秒 p95 直接写成 P2.1 指标。

## AutoDL 复现

确认 Qwen 服务、CNN 权重和归一化文件可用后，执行：

```bash
python -m unittest discover -s tests -v
python scripts/eval_agentic_full.py --validate-only
python scripts/check_full_service.py \
  --timeout 120 \
  --output artifacts/p2_1/service_check.json
```

运行完整严格 Smoke：

```bash
python scripts/eval_agentic_full.py \
  --output artifacts/p2_1/agentic_smoke.json \
  --min-case-pass-rate 1.0
```

真实结果需要继续保留原始 JSON、失败案例、Git commit、GPU 和依赖版本。下一阶段先运行已冻结的正式评测集，再生成对应人工复核工作簿。正式评测合同见 [`p2-1-formal-evaluation-plan.md`](p2-1-formal-evaluation-plan.md)。
