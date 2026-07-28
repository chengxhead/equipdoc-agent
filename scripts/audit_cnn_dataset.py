from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LABELS = {"normal.mat": 0, "inner.mat": 1, "outer.mat": 2, "ball.mat": 3}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CNN split provenance without training.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/p1/cnn_dataset_audit.json")
    args = parser.parse_args()

    with np.load(args.dataset) as data:
        keys = list(data.files)
        arrays = {key: {"shape": list(data[key].shape), "dtype": str(data[key].dtype)} for key in keys}
        label_counts = {}
        for key in ("y_tr", "y_te"):
            if key in data:
                values, counts = np.unique(data[key], return_counts=True)
                label_counts[key] = {str(int(v)): int(c) for v, c in zip(values, counts)}

    raw_files = []
    per_class_sources: Counter[int] = Counter()
    for name, label in LABELS.items():
        path = args.raw_dir / name
        exists = path.exists()
        if exists:
            per_class_sources[label] += 1
        raw_files.append(
            {
                "name": name,
                "label": label,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": _sha256(path) if exists else None,
            }
        )

    provenance_keys = sorted(set(keys).intersection({"groups", "group_ids", "source_ids", "file_ids"}))
    group_split_feasible = all(per_class_sources[label] >= 2 for label in LABELS.values())
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "name": args.dataset.name,
            "size_bytes": args.dataset.stat().st_size,
            "sha256": _sha256(args.dataset),
            "arrays": arrays,
            "label_counts": label_counts,
            "provenance_keys": provenance_keys,
        },
        "raw_sources": raw_files,
        "source_files_per_class": {str(label): per_class_sources[label] for label in LABELS.values()},
        "conclusion": {
            "file_level_group_split_feasible": group_split_feasible,
            "status": "ready" if group_split_feasible and provenance_keys else "blocked",
            "reasons": [
                "Each class currently has only one source .mat file."
                if not group_split_feasible
                else "At least two source files exist per class.",
                "Processed NPZ does not preserve source/group identifiers."
                if not provenance_keys
                else "Processed NPZ preserves provenance identifiers.",
                "Legacy preprocessing randomly split overlapping windows after global normalization.",
            ],
            "required_fix": (
                "Acquire multiple independent source files/conditions per class, attach source_id before "
                "windowing, split by source_id, and fit normalization on training groups only."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["conclusion"], ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
