from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from ..config import Settings


CLASS_NAMES = ["正常", "内圈故障", "外圈故障", "滚动体故障"]
SAMPLE_LEN = 1024


class SignalValidationError(ValueError):
    """Raised when an uploaded signal is outside the public-demo safety boundary."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_signal_path(signal_path: str | Path, settings: Settings) -> Path:
    path = Path(signal_path).expanduser().resolve(strict=True)
    allowed_roots = [settings.sample_root.resolve(), settings.upload_root.resolve()]
    if not any(_is_within(path, root) for root in allowed_roots):
        raise SignalValidationError("Signal path is outside the sample/upload sandbox.")
    if path.suffix.lower() != ".npy":
        raise SignalValidationError("Only .npy signal files are accepted.")
    if not path.is_file():
        raise SignalValidationError("Signal path is not a file.")
    if path.stat().st_size > settings.max_upload_bytes:
        raise SignalValidationError("Signal file exceeds the configured size limit.")
    return path


def _load_signal(path: Path) -> np.ndarray:
    try:
        signal_view = np.load(path, allow_pickle=False, mmap_mode="r")
    except (OSError, ValueError) as exc:
        raise SignalValidationError(
            "Signal file is not a valid non-pickled .npy array."
        ) from exc
    if not (
        np.issubdtype(signal_view.dtype, np.integer)
        or np.issubdtype(signal_view.dtype, np.floating)
    ):
        raise SignalValidationError("Signal array must contain real numeric values.")
    if signal_view.ndim != 1:
        raise SignalValidationError("Signal array must be one-dimensional.")
    if signal_view.size == 0:
        raise SignalValidationError("Signal array is empty.")
    signal = np.array(signal_view, dtype=np.float32, copy=True)
    if not np.isfinite(signal).all():
        raise SignalValidationError("Signal array contains NaN or infinity.")
    return signal


def _signal_summary(signal: np.ndarray) -> dict[str, Any]:
    return {
        "samples": int(signal.size),
        "rms": float(np.sqrt(np.mean(np.square(signal)))),
        "peak_abs": float(np.max(np.abs(signal))),
        "mean": float(np.mean(signal)),
        "std": float(np.std(signal)),
    }


def inspect_bearing_signal(signal_path: str | Path, settings: Settings) -> dict[str, Any]:
    """Inspect a sandboxed signal without running the legacy classifier."""
    path = validate_signal_path(signal_path, settings)
    signal = _load_signal(path)
    summary = _signal_summary(signal)
    warnings = []
    if signal.size < SAMPLE_LEN:
        warnings.append("信号少于1024个采样点；旧分类器会进行补零。")
    elif signal.size > SAMPLE_LEN:
        warnings.append("旧分类器只读取前1024个采样点。")
    if summary["std"] == 0.0:
        warnings.append("信号标准差为0，缺少可用于振动分析的变化。")
    return {
        "status": "ok",
        "mode": "signal_inspection",
        "signal_file": path.name,
        "signal": summary,
        "warnings": warnings,
    }


@lru_cache(maxsize=2)
def _load_model(model_path: str, norm_path: str):
    import torch

    from ..models.bearing_cnn import LightCNN

    model = LightCNN()
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    norm = np.asarray(np.load(norm_path, allow_pickle=False), dtype=np.float64).reshape(-1)
    if norm.size != 2 or not np.isfinite(norm).all() or float(norm[1]) <= 0:
        raise RuntimeError("Normalization artifact must contain finite [mean, positive_std].")
    mean, std = norm
    return model, float(mean), float(std)


def analyze_bearing_signal(signal_path: str | Path, settings: Settings) -> dict[str, Any]:
    path = validate_signal_path(signal_path, settings)
    signal = _load_signal(path)
    summary = _signal_summary(signal)

    if settings.demo_mode:
        return {
            "status": "demo",
            "mode": "demo_fixture",
            "fault_type": "外圈故障（固定演示案例）",
            "confidence": None,
            "probabilities": {},
            "signal": summary,
            "warning": "当前为无模型 Demo 模式；故障类型是固定案例标签，不是本机模型推理结果。",
        }

    if not settings.bearing_model_path.exists() or not settings.bearing_norm_path.exists():
        raise RuntimeError("Bearing model or normalization artifact is missing. Run the health check.")

    model, mean, std = _load_model(
        str(settings.bearing_model_path),
        str(settings.bearing_norm_path),
    )
    if signal.size >= SAMPLE_LEN:
        model_signal = signal[:SAMPLE_LEN]
        preprocessing_note = "Only the first 1024 samples are used by the legacy P0 model."
    else:
        model_signal = np.pad(signal, (0, SAMPLE_LEN - signal.size))
        preprocessing_note = "The signal is zero-padded to 1024 samples by the legacy P0 model."

    import torch

    normalized = (model_signal - mean) / (std + 1e-8)
    inputs = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        probabilities = torch.softmax(model(inputs), dim=1).squeeze().numpy()
    predicted = int(probabilities.argmax())
    return {
        "status": "ok",
        "mode": "legacy_cnn",
        "fault_type": CLASS_NAMES[predicted],
        "confidence": float(probabilities[predicted]),
        "probabilities": {
            CLASS_NAMES[index]: float(value) for index, value in enumerate(probabilities)
        },
        "signal": summary,
        "warning": preprocessing_note,
    }
