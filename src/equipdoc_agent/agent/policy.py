from __future__ import annotations


CURRENT_SIGNAL_MARKERS = (
    "这段",
    "这个",
    "该段",
    "当前",
    "上传",
    "刚测",
    "刚采",
    "文件",
    "路径",
    ".npy",
)
DIAGNOSIS_ACTION_MARKERS = (
    "诊断",
    "分析",
    "判断",
    "分类",
    "识别",
    "检查",
)
DIAGNOSIS_OUTPUT_MARKERS = (
    "故障类型",
    "故障概率",
    "置信度",
    "诊断结论",
    "诊断报告",
    "是否正常",
    "有没有故障",
    "有没有异常",
    "判断问题",
)
KNOWLEDGE_QUESTION_MARKERS = (
    "为什么",
    "为何",
    "什么",
    "哪些",
    "如何",
    "怎么",
    "原因",
    "机理",
    "原理",
    "区别",
    "一般",
    "通常",
    "常见",
    "表现",
    "应关注",
    "应复核",
    "应怎样",
    "应该",
)
IMPERATIVE_MARKERS = (
    "请诊断",
    "帮我诊断",
    "进行诊断",
    "做一次诊断",
    "做一次轴承诊断",
    "调用诊断",
    "直接诊断",
    "帮我判断",
    "请判断",
    "帮我分析",
    "请分析",
)
OUTPUT_REQUEST_MARKERS = (
    "给出",
    "输出",
    "生成",
    "告诉我",
)


def requests_diagnosis(user_text: str) -> bool:
    normalized = (user_text or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    current_signal_request = any(marker in lowered for marker in CURRENT_SIGNAL_MARKERS)
    diagnosis_action = any(marker in lowered for marker in DIAGNOSIS_ACTION_MARKERS)
    diagnosis_output = any(marker in lowered for marker in DIAGNOSIS_OUTPUT_MARKERS)
    if current_signal_request and (diagnosis_action or diagnosis_output):
        return True

    knowledge_question = any(marker in lowered for marker in KNOWLEDGE_QUESTION_MARKERS)
    if knowledge_question:
        return False

    if any(marker in lowered for marker in IMPERATIVE_MARKERS):
        return True
    return diagnosis_output and any(marker in lowered for marker in OUTPUT_REQUEST_MARKERS)


def should_run_diagnosis(user_text: str, signal_path: str | None) -> bool:
    if not signal_path:
        return False
    if not (user_text or "").strip():
        return True
    return requests_diagnosis(user_text)


def normalize_review_decision(decision: str) -> str:
    normalized = (decision or "").strip().lower()
    if normalized not in {"approve", "reject"}:
        raise ValueError("Review decision must be approve or reject.")
    return normalized
