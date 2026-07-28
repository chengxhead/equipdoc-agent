from __future__ import annotations


DIAGNOSIS_KEYWORDS = (
    "诊断",
    "分析",
    "看看",
    "判断",
    "轴承",
    "故障",
    "状态",
    "有没有问题",
    "置信度",
    "概率",
    "维修建议",
)


def should_run_diagnosis(user_text: str, signal_path: str | None) -> bool:
    if not signal_path:
        return False
    normalized = (user_text or "").strip()
    if not normalized:
        return True
    return any(keyword in normalized for keyword in DIAGNOSIS_KEYWORDS)


def normalize_review_decision(decision: str) -> str:
    normalized = (decision or "").strip().lower()
    if normalized not in {"approve", "reject"}:
        raise ValueError("Review decision must be approve or reject.")
    return normalized

