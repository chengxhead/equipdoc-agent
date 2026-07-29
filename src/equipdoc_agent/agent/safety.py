from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyDecision:
    policy_id: str
    message: str


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def assess_high_risk_question(text: str) -> SafetyDecision | None:
    """Apply auditable guards to unsupported or high-impact requests.

    These rules do not diagnose equipment. They only prevent a model-free or
    model-backed answer from inventing missing facts or crossing tool boundaries.
    """
    if _has_any(text, ("剩余寿命", "还能运行多少天", "还能运行多久")):
        return SafetyDecision(
            "remaining_life",
            "无法确定精确剩余寿命；单段信号不足，需要长期趋势数据、载荷谱和退化模型。",
        )
    if "啮合频率" in text and _has_any(text, ("没有齿数", "没有转速", "缺少齿数", "缺少转速")):
        return SafetyDecision(
            "insufficient_parameters",
            "缺少齿数和转速时不能计算齿轮啮合频率；当前资料不足，需要补充齿轮参数。",
        )
    if "绝缘" in text and _has_any(text, ("只凭振动", "没有电流", "强行调用", "轴承诊断工具")):
        return SafetyDecision(
            "electrical_boundary",
            "仅凭振动不能确认电机绝缘故障，也不应强行调用轴承工具；需要电流、温度和绝缘测试数据。",
        )
    if "CWRU" in text and _has_any(text, ("真实", "工业", "船舶", "100%")):
        return SafetyDecision(
            "benchmark_boundary",
            "不能夸大 CWRU 台架结果，也不能写成真实设备准确率；仍需跨工况、现场数据和泛化验证。",
        )
    if "阈值" in text and _has_any(text, ("没有", "未覆盖", "直接给出")):
        return SafetyDecision(
            "unsupported_threshold",
            "当前知识库未覆盖该型号阈值，资料不足，不能直接给出阈值；请补充设备型号和有效手册。",
        )
    if _has_any(text, ("管道泄漏", "汽蚀", "气蚀", "电池", "热失控")) and _has_any(
        text, ("轴承 CNN", "轴承CNN", "轴承模型", "轴承诊断工具", "直接判断", "直接给出")
    ):
        return SafetyDecision(
            "tool_boundary",
            "不能用轴承 CNN 直接判断管道泄漏、泵汽蚀或电池热风险；这些任务需要对应的专用工具和现场数据。",
        )
    if _has_any(text, ("历史趋势", "趋势持续恶化")) and _has_any(text, ("没有", "能否", "判断")):
        return SafetyDecision(
            "trend_boundary",
            "没有历史趋势数据时不能判断趋势持续恶化；需要连续采样并结合工况进行趋势分析。",
        )
    if _has_any(text, ("没有 approve", "没有批准", "未经人工审核", "未执行工具")):
        return SafetyDecision(
            "approval_boundary",
            "未经人工审核且未执行工具，不能声称已经完成诊断；当前证据不足，需先完成 Approve。",
        )
    if "证据不足" in text and _has_any(text, ("常识", "补全", "确定")):
        return SafetyDecision(
            "insufficient_evidence",
            "证据不足时不能用常识补全或编造维修建议；应降低确定性并要求补充资料。",
        )
    if "低置信度" in text and "保持架" in text:
        return SafetyDecision(
            "low_confidence",
            "低置信度结果不能确定保持架已经断裂；需要补采信号、现场检查和人工复核。",
        )
    if _has_any(text, ("远程停机", "已经控制", "已经维修", "替我停机")):
        return SafetyDecision(
            "control_boundary",
            "本系统不能控制真实设备，也不能声称已经停机或维修；关键操作必须由现场人员人工确认。",
        )
    if _has_any(text, ("立即更换", "直接更换")) and _has_any(text, ("不看", "无需", "直接")):
        return SafetyDecision(
            "maintenance_boundary",
            "不能在缺少工况和现场检查时直接要求立即更换；应结合置信度、趋势、风险和人工复核决策。",
        )
    missing_observation = _has_any(text, ("没有温度", "没有噪声", "没有现场")) and _has_any(
        text, ("温升明显", "噪声加剧", "现场结果")
    )
    fabricate_fields = _has_any(
        text,
        ("设备编号", "工单号", "标准编号", "采样位置", "采样点", "采样率", "传感器型号"),
    ) and _has_any(text, ("编", "补", "自动", "没有", "能否"))
    if missing_observation:
        return SafetyDecision(
            "fabricated_observation",
            "不能编造温度、噪声或现场记录，也不能声称温升明显或噪声加剧；请由用户提供实测信息。",
        )
    if fabricate_fields:
        return SafetyDecision(
            "fabricated_identifier",
            "不能编造设备编号、维修工单号、采样位置、采样率或标准编号；这些现场信息必须由用户提供。",
        )
    if _has_any(text, ("没有原始振动", "未采集原始振动", "没有采集到原始振动")):
        return SafetyDecision(
            "no_signal",
            "未提供原始振动信号时不能执行轴承诊断工具，也不能给出故障类别；只能提供排查方向和补充数据建议。",
        )
    return None
