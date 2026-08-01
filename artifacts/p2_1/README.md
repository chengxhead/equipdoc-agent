# P2.1 评测证据

本目录保存 P2.1 在 AutoDL RTX 4090 上运行真实 Qwen + CNN 的固定 Smoke 与正式评测证据。正式评测集为 56 cases / 64 turns，冻结 SHA-256 为 `7f7613ad09819300dbc6edbb98e9d2383d774a3f0cbfee4c939573392dbb23b8`；最终自动评测代码基线为 `f34bc340401029cf5ca510fe76641f4a8d59a6cb`。

## 正式评测文件

| 文件 | 用途 | 结果 / 状态 |
|---|---|---|
| `formal_service_check.json` | 正式运行前的模型服务、GPU 和探针记录 | `ready=true`，探针 `READY` |
| `agentic_eval_preview_2.json` | 正式集前 2 个案例预检 | commit `387e6f4`，2/2 |
| `agentic_eval_stratified_preview.json` | 7 组分层预检 | commit `387e6f4`，8/8 |
| `agentic_eval_before_general_fixes_387e6f4.json` | 首次完整真实基线 | 64 turns，57/64，失败 7 turns |
| `agentic_eval_failed_subset_after_routing_fix_de7d3d3.json` | 首轮通用路由修复后的定向回归 | 保留中间失败与修复证据 |
| `agentic_eval_failed_subset_after_fix.json` | 完整证据覆盖修复后的定向回归 | commit `82e9a5e`，10/10 |
| `agentic_eval_before_field_review_fix_82e9a5e.json` | 最后一次修复前的完整基线 | 64 turns，63/64，仅 `formal_014` 失败 |
| `agentic_eval_formal_014_after_fix.json` | `formal_014` 聚焦现场复核证据回归 | commit `f34bc34`，1/1 |
| `agentic_eval.json` | 最终完整正式自动基线 | commit `f34bc34`，64/64，退出码 0 |
| `agentic_eval_human_review.xlsx` | 预填正式人工复核工作簿 | 0/64 已复核，人工指标保持空白 |

## Smoke 文件

| 文件 | 用途 | 结果 / 状态 |
|---|---|---|
| `service_check.json` | Smoke 模型服务、GPU 和探针记录 | `ready=true`，探针 `READY` |
| `smoke_failure_overclarification.json` | 初始真实失败 | commit `6ed1185`，0/2 |
| `smoke_2_after_overclarification_fix.json` | 过度澄清修复后的局部回归 | commit `af17605`，2/2 |
| `smoke_failure_hidden_tool_observation.json` | 完整 Smoke 的第二类真实失败 | commit `af17605`，7/8 |
| `agentic_smoke.json` | 最终严格 Smoke 基线 | commit `efc1c54`，8/8 |
| `agentic_smoke_human_review.xlsx` | 预填 Smoke 人工复核工作簿 | 0/8 已复核，人工指标保持空白 |

## SHA-256

| 文件 | SHA-256 |
|---|---|
| `agentic_eval.json` | `5050c3b781f615d8d0622c7ba83cbc0f16f73c0502e24e3dab4d26495548f6ae` |
| `agentic_eval_before_field_review_fix_82e9a5e.json` | `2c76a0c3ebf825777a57e726de79b4ee2e5512db851afaad16837629f92609cd` |
| `agentic_eval_before_general_fixes_387e6f4.json` | `8999ce61ade0193029a9781fea7a3d6dced57fce22f0b94d73ad5fa39d897faf` |
| `agentic_eval_failed_subset_after_fix.json` | `e1f421ac104fd1e44d57afb0b74fe5adaaff07ae147e2493f5adf61ef2e89f14` |
| `agentic_eval_failed_subset_after_routing_fix_de7d3d3.json` | `ae54e230467ae1fa1f0201cb889b5feda1f09d8367a5465f2da83a3d370c9575` |
| `agentic_eval_formal_014_after_fix.json` | `50d7240ce042b8fd80ea882731515f90d3f20edbd7633a1545a284bc720af5e2` |
| `agentic_eval_human_review.xlsx` | `02877940edd93d86f5955d0d69c736b4cbd41f71861a1703bd4d998939f15e61` |
| `agentic_eval_preview_2.json` | `d2cf24a7b7180b92c1e4423108a57ad1e1aaf2a413e3d57ac8e4d338b8660528` |
| `agentic_eval_stratified_preview.json` | `826f2d80fc7b522dc23ba1b6a652fec76da790db170187c83a1713eaab0b1da9` |
| `formal_service_check.json` | `e003d1107ed342e42900fba7d474f814ac07740abebc72c59046fe100efc5702` |
| `agentic_smoke.json` | `2d83b0bd2c3a5685dcb4994717b6bb072512eae9055e45bd3c57531e9e3187be` |
| `agentic_smoke_human_review.xlsx` | `eca02b3e977f1ffc7edad303dc7023fa4dd483e35bd4dfa32e2c933a3404c1bf` |
| `service_check.json` | `514a1a089fb58bcb9b18cc5f0c3ffbbe7be28deda9240a721910ebd57f065739` |
| `smoke_2_after_overclarification_fix.json` | `ebd90c410a8f4d91d0702e884169d5bad3fbd4e97a44fa708d01e5687a197a9a` |
| `smoke_failure_hidden_tool_observation.json` | `fa8f73e78fa22822e92a82691e01178de46e8ea3aa61acb294e72eac90cb3de5` |
| `smoke_failure_overclarification.json` | `3a81779682756c4ee102aac2d019bd257bb19f4e7e5426170527a1257a030079` |

工作簿哈希对应“人工评分全部留空”的发布版本；填写评分后文件和哈希会自然变化。

## 解释边界

- 最终 64/64 是冻结正式集的自动结构化合同结果，不是人工回答正确率。
- 52 个进入规划器的 turn 中，25 个模型计划在首轮或重试后被接受，27 个走确定性 fallback。
- 38 个需要证据回答的 turn 全部走 `extractive_fallback`；自动引用有效不代表自然语言综合已稳定成功。
- 工具调用为知识检索 38 次、只读信号检查 6 次、轴承诊断 12 次。
- CNN 只用于验证受审工具链路，本次未评估工业诊断准确率。
- 正式人工复核当前为 0/64，尚不能报告人工正确率、人工 groundedness 或引用有用率。

完整口径见 [`docs/p2-1-agentic-evaluation-report.md`](../../docs/p2-1-agentic-evaluation-report.md)。
