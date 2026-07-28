# P1 后续操作清单（本地与 AutoDL）

## A. 本地：提交本次 P1

先执行完整验证：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\eval_agent_workflow.py --min-case-pass-rate 0.85
.\.venv\Scripts\python.exe scripts\eval_rag_retrieval.py --min-hit-at-5 0.90 --min-mrr-at-10 0.75
```

三个命令都正常结束后，在 VS Code 的“源代码管理”页面检查改动。应包含源码、评测脚本、三个 JSON 证据文件、P1 报告、操作清单、测试和 CI；不应出现 `.env`、模型权重、向量库、上传文件或旧原始数据。

建议提交信息：

```text
feat: add reproducible P1 evaluation suite
```

提交后点击“同步更改”，再到 GitHub Actions 确认 Python 3.10、3.11、3.12 三个任务均为绿色。

## B. AutoDL：当前不要直接重跑 CNN 准确率

现有四个 `.mat` 文件每类只有一个来源，无法形成可信的文件级训练/测试拆分。继续用旧 `dataset.npz` 训练，只会复现有泄漏风险的成绩，不能增加作品可信度。

先准备新的数据清单，至少包含：

| 字段 | 示例 | 用途 |
|---|---|---|
| source_id | bearing_01_load2 | Group Split |
| label | inner_race | 分类标签 |
| rpm | 1772 | 工况分析 |
| load | 2hp | 跨工况测试 |
| sensor | drive_end | 采样位置 |
| sample_rate | 12000 | 信号处理复现 |
| source_url/license | 数据来源与许可 | 公开合规 |

每个类别至少要有多个独立 `source_id`。如果多个文件只是同一段长信号再次切片，仍视为同一组。

## C. AutoDL：新数据到位后的执行顺序

1. 上传数据到 AutoDL 私有目录，不上传 GitHub；
2. 生成带 `source_id` 的 manifest；
3. 先按组拆分，再切窗；
4. 只在训练组计算均值和标准差；
5. 训练 CNN，保存最佳验证集权重；
6. 对完全独立测试组输出混淆矩阵与每类指标；
7. 把汇总 JSON、图表和环境信息下载回本地；
8. GitHub 只提交小型结果证据，不提交原始数据和权重。

## D. P1 下一小步的优先级

1. 补充通用温升排查、泵汽蚀、电池热失控、无信号诊断边界四类知识；
2. 为 20 条高风险/越界问题做人审表，统计 groundedness、拒答正确性和引用覆盖；
3. 使用真实 Full 模式记录模型版本、GPU、p50/p95 延迟和失败样例；
4. 数据条件满足后再做 CNN Group Split。

不要在这四项完成前把 Demo 指标写成真实生产能力。
