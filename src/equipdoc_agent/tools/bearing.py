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
    signal = np.load(path, allow_pickle=False)
    if not np.issubdtype(signal.dtype, np.number):
        raise SignalValidationError("Signal array must contain numeric values.")
    signal = np.asarray(signal, dtype=np.float32).reshape(-1)
    if signal.size == 0:
        raise SignalValidationError("Signal array is empty.")
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


@lru_cache(maxsize=2)
def _load_model(model_path: str, norm_path: str):
    import torch

    from ..models.bearing_cnn import LightCNN

    model = LightCNN()
    try:
        state = torch.load(model_path, map_location="cpu", weights_only=True)
    except TypeError:
        state = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    mean, std = np.load(norm_path, allow_pickle=False)
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

