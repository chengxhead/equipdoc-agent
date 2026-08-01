from __future__ import annotations

import re
from pathlib import Path
from typing import Any


WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)\b[A-Z]:[\\/][^\s\"'`]+")
POSIX_PRIVATE_PATH = re.compile(r"(?<![A-Za-z0-9])/(?:root|home|tmp|var|opt)/[^\s\"'`]+")
BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[^\s,;\"']+")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|token)\b\s*[:=]\s*[^\s,;\"']+"
)


def redact_sensitive_text(value: Any, *, project_root: Path | None = None) -> str:
    """Remove server-local filesystem paths from user-visible text."""
    text = str(value)
    if project_root is not None:
        root = str(project_root.resolve())
        text = text.replace(root, "[REDACTED_PATH]")
        text = text.replace(root.replace("\\", "/"), "[REDACTED_PATH]")
    text = WINDOWS_ABSOLUTE_PATH.sub("[REDACTED_PATH]", text)
    text = POSIX_PRIVATE_PATH.sub("[REDACTED_PATH]", text)
    text = BEARER_TOKEN.sub("Bearer [REDACTED]", text)
    text = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text


def public_exception_message(exc: Exception, *, project_root: Path | None = None) -> str:
    """Return actionable input errors and hide unexpected implementation details."""
    if isinstance(exc, (ValueError, FileNotFoundError)):
        message = redact_sensitive_text(exc, project_root=project_root).strip()
        return message[:500] or "输入未通过校验。"
    return f"{type(exc).__name__}: 请求未能完成，请检查服务日志或运行健康检查。"
