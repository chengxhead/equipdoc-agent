# P2.1 Agentic 升级交接

> 更新时间：2026-08-01
> 当前结论：P2.1 工程实现、固定 Smoke 和冻结正式集的自动验收已经完成；正式人工质量复核工作簿已生成，但当前为 0/64，不能报告人工正确率。

## 1. 项目要解决什么

EquipDoc-Agent 面向机电设备运维场景，把自然语言交互、振动信号工具、知识检索、人工审核和证据化回答组织为可审计、可降级的 LangGraph 工作流。

P2.1 的目标不是让 Qwen 任意调用工具，而是在确定性安全边界内增加受限 Agentic 能力：

- Qwen 输出严格 JSON 意图与计划；
- 本地 Schema、白名单、参数和最大步数校验决定计划能否执行；
- `inspect_signal` 与 `search_maintenance_knowledge` 是只读工具；
- `diagnose_bearing` 必须经过 Approve/Reject；
- 工具观察后由 Qwen 决定继续调用允许的工具、回答或澄清；
- 同一 `thread_id` 保存有界结构化记忆；
- 技术结论必须有合法逐句引用；
- 规划或回答两次不合格时进入显式确定性 fallback；
- 剩余寿命、远程控制、跨设备误用和信息编造继续由本地安全策略拦截。

P2.1 使用 OpenAI-compatible 聊天接口上的严格 JSON 规划，不是原生 Function Calling。

## 2. 已完成的工程实现

### 2.1 规划与校验

- 结构化意图和多步骤计划 Prompt；
- JSON 提取、Schema 校验、重试与确定性 fallback；
- intent、工具名、参数、重复 step、依赖、循环和最大步数检查；
- 删除模型提供的本地路径，真实信号路径仅由系统注入；
- 自包含知识问题、诊断、只读检查、澄清和安全边界的通用路由。

### 2.2 三工具与人工审核

- `inspect_signal`：返回 samples、RMS、peak、mean、std 和长度警告，不运行 CNN；
- `diagnose_bearing`：加载 CNN，输出类别、置信度、概率与信号摘要，执行前必须人工审核；
- `search_maintenance_knowledge`：返回结构化证据与 `doc_id#chunk_id` 引用；
- 工具观察经过脱敏，审核载荷不暴露服务器绝对路径。

### 2.3 图、记忆与回答

- 独立 `agentic_graph.py`，只在 Full + Agentic 显式开启；
- 工具观察后决策与最大工具步数限制；
- 同线程保存当前设备、文件名、诊断结果、证据和待澄清信息；
- 新文件清理旧诊断记忆；
- 工具事实与知识解释分开渲染；
- 引用、术语、数字、完整证据覆盖和安全边界校验；
- 草稿失败重试一次，再失败返回可逐字回查的抽取式证据。

### 2.4 兼容性

| 配置 | 实际模式 |
|---|---|
| `EQUIPDOC_DEMO_MODE=true` | 无模型 Demo |
| `EQUIPDOC_DEMO_MODE=false`、`EQUIPDOC_AGENTIC_MODE=false` | 已发布 P2 baseline |
| `EQUIPDOC_DEMO_MODE=false`、`EQUIPDOC_AGENTIC_MODE=true` | P2.1 Agentic |

最终代码基线 `f34bc34` 上 93 项 `unittest` 全部通过。

## 3. 已完成的真实模型验证

### 3.1 固定 Smoke

- 输入：7 cases / 8 turns；
- 最终 commit：`efc1c54`；
- 自动结果：8/8；
- 平均 / p95：10.107 / 22.286 秒；
- 6 个规划 turn 中 2 个首轮成功、4 个确定性 fallback；
- 4 个证据回答全部 `extractive_fallback`；
- 保留了过度澄清和成功工具观察被覆盖两类真实失败。

### 3.2 冻结正式集

- 输入：[`data/eval/agentic_eval.jsonl`](../data/eval/agentic_eval.jsonl)；
- 规模：56 cases / 64 turns；
- SHA-256：`7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8`；
- 运行环境：AutoDL RTX 4090，Qwen `qwen-equipdoc`，本地 CNN；
- 最终 commit：`f34bc34`；
- 最终自动结果：64/64，严格阈值退出码 0；
- 平均 / p50 / p95：7.472 / 8.541 / 16.758 秒；
- 52 个规划 turn 中 25 个模型计划被首轮或重试接受，27 个确定性 fallback；
- 38 个证据回答全部 `extractive_fallback`；
- 工具调用：知识检索 38、信号检查 6、轴承诊断 12。

正式失败演进：

| Commit | 完整结果 | 失败 |
|---|---:|---|
| `387e6f4` | 57/64 | 7 turns |
| `82e9a5e` | 63/64 | 仅 `formal_014` |
| `f34bc34` | 64/64 | 0 |

评测集在修复期间没有修改。所有基线、定向回归、修复前全量和最终全量 JSON 都保留在 [`artifacts/p2_1/`](../artifacts/p2_1/README.md)。

## 4. 当前证据入口

| 用途 | 文件 |
|---|---|
| 正式最终 JSON | [`artifacts/p2_1/agentic_eval.json`](../artifacts/p2_1/agentic_eval.json) |
| 正式人工复核工作簿 | [`artifacts/p2_1/agentic_eval_human_review.xlsx`](../artifacts/p2_1/agentic_eval_human_review.xlsx) |
| 正式服务探针 | [`artifacts/p2_1/formal_service_check.json`](../artifacts/p2_1/formal_service_check.json) |
| 全部证据与 SHA-256 | [`artifacts/p2_1/README.md`](../artifacts/p2_1/README.md) |
| 完整评估报告 | [`docs/p2-1-agentic-evaluation-report.md`](p2-1-agentic-evaluation-report.md) |
| 评测合同与执行记录 | [`docs/p2-1-formal-evaluation-plan.md`](p2-1-formal-evaluation-plan.md) |
| 本地实现记录 | [`docs/p2-1-local-implementation.md`](p2-1-local-implementation.md) |

## 5. 尚未完成

### 5.1 正式人工复核

`agentic_eval_human_review.xlsx` 已预填 64 个 turn，但所有人工评分为空，当前进度 0/64。需要逐 turn 评估：

- 意图是否正确；
- 工具选择是否合理；
- 回答事实是否正确；
- 证据是否支持回答；
- 引用是否有用；
- 安全处理是否适当。

在人工列未填写前，不得声称人工回答正确率、人工 groundedness、引用有用率或安全适当率。

### 5.2 后续质量优化

- 降低 51.9% 的确定性规划 fallback；
- 提高自然语言证据综合通过率，减少证据回答 100% 抽取式 fallback；
- 多次重复正式集以评估生成稳定性和延迟波动；
- 为知识库补充权威来源和版本信息；
- 按原始文件和工况做 CNN Group Split，再讨论工业诊断准确率。

这些属于 P2.1 质量提升或后续研究，不影响“工程实现与正式自动验收已完成”的结论。

## 6. 当前 Git 与提交边界

Windows 主仓库在整理正式证据前的代码状态为：

```text
f34bc34 (HEAD -> main, origin/main, origin/HEAD) fix: prioritize focused field review evidence
```

本轮待提交内容应只包含：

- `artifacts/p2_1/` 新增正式 JSON、正式复核工作簿与更新后的说明；
- P2.1 README、架构、评测报告、正式计划、本地实现和本交接文档更新。

下列三个 P1 JSON 是用户此前的独立改动，必须继续保留但不得加入 P2.1 提交：

- `artifacts/p1/agent_workflow.json`
- `artifacts/p1/rag_retrieval.json`
- `artifacts/p1/safety_grounding.json`

禁止：

- `git reset --hard` 或 `git checkout --` 丢弃用户改动；
- 提交模型权重、`.env`、虚拟环境、缓存、压缩包或 AutoDL 私有路径；
- 未经用户确认直接 push。

## 7. 完成度判断

- P2.1 核心工程实现：完成；
- Demo / P2 / P2.1 自动回归：完成；
- 固定真实模型 Smoke：完成；
- 冻结正式集自动评测、失败分析与证据归档：完成；
- 正式人工质量复核：未完成，0/64；
- CNN 工业准确率与生产部署验证：不在本轮完成范围。

因此可以宣布“P2.1 工程与正式自动验收完成”，不能宣布“人工质量验证全部完成”或“系统达到工业部署要求”。

## 8. 下一次继续时的顺序

1. 运行 `git status --short --branch`，确认只有 P2.1 待提交文件和三个未暂存 P1 改动；
2. 运行 93 项 `unittest`、正式集 `--validate-only`、隐私扫描和 `git diff --check`；
3. 在 VSCode Source Control 中仅暂存本交接第 6 节列出的 P2.1 文件；
4. 提交并推送正式评测证据与文档；
5. 打开 `agentic_eval_human_review.xlsx` 开始 64-turn 人工复核；
6. 人工复核完成后单独提交评分后的工作簿与人工结论报告。

## 9. 可用于简历的当前表述

可以使用：

> 为 Qwen2.5-7B 增加严格 JSON 意图规划、三工具白名单、工具观察后决策和 LangGraph 短期任务记忆，通过人工审批、路径沙箱、逐句引用校验和确定性降级约束执行；构建并冻结 56-case / 64-turn Agentic 正式评测，在 RTX 4090 真实 Qwen + CNN 环境中实现 64/64 自动合同通过，p95 16.76 秒，并保留 57/64 → 63/64 → 64/64 的失败修复证据。

必须同时说明：自动合同通过不等于人工回答正确率；当前人工复核为 0/64，51.9% 规划 turn 使用确定性 fallback，38 个证据回答全部使用抽取式 fallback。
