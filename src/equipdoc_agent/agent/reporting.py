from __future__ import annotations

from typing import Any


def _suggestion(fault_type: str) -> str:
    if "正常" in fault_type:
        return "未发现目标故障类别的明显特征；仍应结合趋势、工况和现场点检确认。"
    if "滚动体" in fault_type:
        return "检查滚动体、保持架、润滑污染和局部剥落，并安排复测与包络谱复核。"
    if "外圈" in fault_type:
        return "检查外圈滚道、轴承座配合、安装应力和润滑状态，必要时安排计划停机复核。"
    if "内圈" in fault_type:
        return "检查内圈、轴颈配合、冲击载荷和润滑状态，并结合转速与负载变化复测。"
    return "补充运行工况、采样信息和趋势数据后再进行工程判断。"


def render_diagnosis_report(
    result: dict[str, Any],
    signal_name: str,
    evidence: list[dict[str, Any]] | None = None,
) -> str:
    evidence = evidence or []
    fault_type = str(result.get("fault_type", "未提供"))
    confidence = result.get("confidence")
    confidence_text = "未提供" if confidence is None else f"{float(confidence):.2%}"
    probabilities = result.get("probabilities") or {}
    probability_text = "；".join(
        f"{name}: {float(value):.2%}" for name, value in probabilities.items()
    ) or "未提供"

    evidence_lines = []
    for index, item in enumerate(evidence, start=1):
        source = f"{item.get('doc_id', 'unknown')}#{item.get('chunk_id', 'unknown')}"
        snippet = str(item.get("text", "")).replace("\n", " ").strip()[:180]
        evidence_lines.append(f"- [{index}] {source}：{snippet}")
    evidence_text = "\n".join(evidence_lines) or "- 当前未检索到可用证据。"

    demo_warning = ""
    if result.get("mode") == "demo_fixture":
        demo_warning = "\n> **Demo 提示：故障标签为固定回放，不是模型推理结果。**\n"

    return f"""# 诊断报告
{demo_warning}
## 诊断结论

- 信号文件：{signal_name}
- 故障类型：{fault_type}
- 模型置信度：{confidence_text}
- 类别概率：{probability_text}

## 检索证据

{evidence_text}

## 处理建议

- {_suggestion(fault_type)}
- 该结果仅用于辅助判断，关键维修操作必须结合现场点检、复测数据和人工审核。

## 已知边界

- 设备编号、采样位置、传感器型号、采样率、运行工况和维修历史均未提供。
- 不根据单段信号推断精确剩余寿命、工单编号或未提供的历史趋势。
- 工具警告：{result.get('warning', '无')}
"""
