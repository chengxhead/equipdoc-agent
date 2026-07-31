# P2.1 评测证据

本目录保存 2026-07-31 在 AutoDL RTX 4090 上运行 P2.1 真实 Qwen + CNN 固定 Smoke Test 的可追溯证据。最终代码基线为 `efc1c540e04c6b3b605455bd9fff9ac4ac360b4e`。

## 文件说明

| 文件 | 用途 | 结果 / 状态 |
|---|---|---|
| `service_check.json` | 模型服务、GPU 和探针记录 | `ready=true`，探针 `READY` |
| `smoke_failure_overclarification.json` | 初始真实失败 | commit `6ed1185`，2 turns，0/2 |
| `smoke_2_after_overclarification_fix.json` | 过度澄清修复后的局部回归 | commit `af17605`，2 turns，2/2 |
| `smoke_failure_hidden_tool_observation.json` | 完整 Smoke 的第二类真实失败 | commit `af17605`，8 turns，7/8 |
| `agentic_smoke.json` | 最终严格 Smoke 基线 | commit `efc1c54`，8 turns，8/8 |
| `agentic_smoke_human_review.xlsx` | 预填人工复核工作簿 | 0/8 已复核，人工指标保持空白 |

## SHA-256

| 文件 | SHA-256 |
|---|---|
| `agentic_smoke.json` | `2d83b0bd2c3a5685dcb4994717b6bb072512eae9055e45bd3c57531e9e3187be` |
| `agentic_smoke_human_review.xlsx` | `eca02b3e977f1ffc7edad303dc7023fa4dd483e35bd4dfa32e2c933a3404c1bf` |
| `service_check.json` | `514a1a089fb58bcb9b18cc5f0c3ffbbe7be28deda9240a721910ebd57f065739` |
| `smoke_2_after_overclarification_fix.json` | `ebd90c410a8f4d91d0702e884169d5bad3fbd4e97a44fa708d01e5687a197a9a` |
| `smoke_failure_hidden_tool_observation.json` | `fa8f73e78fa22822e92a82691e01178de46e8ea3aa61acb294e72eac90cb3de5` |
| `smoke_failure_overclarification.json` | `3a81779682756c4ee102aac2d019bd257bb19f4e7e5426170527a1257a030079` |

工作簿的哈希对应“人工评分全部留空”的发布版本；填写评分后文件和哈希会自然变化。

## 解释边界

- 8/8 是固定 Smoke 集的自动结构化检查结果，不是人工回答正确率。
- 6 个进入规划器的 turn 中只有 2 个首轮规划成功，4 个走确定性 fallback。
- 4 个需要证据回答的 turn 全部走 `extractive_fallback`。
- CNN 只用于验证受审工具链路，本次未评估工业诊断准确率。
- 更大规模正式评测和人工复核仍待完成。

完整口径见 [`docs/p2-1-agentic-evaluation-report.md`](../../docs/p2-1-agentic-evaluation-report.md)。
