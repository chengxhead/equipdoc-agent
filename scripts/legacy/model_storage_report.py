import argparse
import json
import os
from collections import defaultdict
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Report model directory/file storage size.")
    parser.add_argument("--paths", nargs="+", required=True, help="Model directories or files.")
    parser.add_argument("--top_k", type=int, default=20)
    parser.add_argument("--output", default="model_storage_report.json")
    return parser.parse_args()


def format_bytes(num_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024


def collect_path(path):
    path = os.path.abspath(path)
    files = []

    if os.path.isfile(path):
        files.append(path)
    else:
        for root, _, names in os.walk(path):
            for name in names:
                files.append(os.path.join(root, name))

    total_bytes = 0
    by_ext = defaultdict(int)
    file_infos = []

    for file_path in files:
        try:
            size = os.path.getsize(file_path)
        except OSError:
            continue
        total_bytes += size
        ext = os.path.splitext(file_path)[1].lower() or "<no_ext>"
        by_ext[ext] += size
        file_infos.append(
            {
                "path": file_path,
                "size_bytes": size,
                "size_human": format_bytes(size),
            }
        )

    file_infos.sort(key=lambda item: item["size_bytes"], reverse=True)

    return {
        "path": path,
        "exists": os.path.exists(path),
        "is_file": os.path.isfile(path),
        "file_count": len(file_infos),
        "total_bytes": total_bytes,
        "total_human": format_bytes(total_bytes),
        "by_extension": {
            ext: {"bytes": value, "human": format_bytes(value)}
            for ext, value in sorted(by_ext.items(), key=lambda item: item[1], reverse=True)
        },
        "largest_files": file_infos,
    }


def main():
    args = parse_args()
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paths": [],
    }

    for path in args.paths:
        item = collect_path(path)
        item["largest_files"] = item["largest_files"][: args.top_k]
        report["paths"].append(item)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("===== Model Storage Report =====")
    for item in report["paths"]:
        print(f"{item['path']}: {item['total_human']} ({item['file_count']} files)")
        for ext, value in item["by_extension"].items():
            print(f"  {ext}: {value['human']}")
    print(f"\nSaved: {args.output}")


if __name__ == "__main__":
    main()

