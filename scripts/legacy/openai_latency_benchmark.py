import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime


DEFAULT_PROMPTS = [
    "轴承外圈故障一般有什么振动特征？",
    "我的设备振动信号在 data/test_signal.npy，帮我判断轴承有没有问题。",
    "如果设备点检发现温升异常，应从哪些方面排查？",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark an OpenAI-compatible chat service.")
    parser.add_argument("--base_url", default="http://localhost:8000/v1")
    parser.add_argument("--model", default="qwen-equipdoc")
    parser.add_argument("--max_tokens", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", default="openai_latency_benchmark.json")
    return parser.parse_args()


def post_json(url, payload, timeout=180):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat_once(args, prompt):
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    url = args.base_url.rstrip("/") + "/chat/completions"
    started = time.perf_counter()
    data = post_json(url, payload)
    elapsed = time.perf_counter() - started

    message = data.get("choices", [{}])[0].get("message", {})
    content = message.get("content") or ""
    usage = data.get("usage") or {}
    completion_tokens = usage.get("completion_tokens")

    return {
        "prompt": prompt,
        "latency_sec": elapsed,
        "content_chars": len(content),
        "completion_tokens": completion_tokens,
        "tokens_per_sec": (completion_tokens / elapsed) if completion_tokens else None,
        "content_preview": content[:300],
    }


def average(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def main():
    args = parse_args()
    results = []

    print("===== Warmup =====")
    for index in range(args.warmup):
        prompt = DEFAULT_PROMPTS[index % len(DEFAULT_PROMPTS)]
        try:
            result = chat_once(args, prompt)
            print(f"warmup {index + 1}: {result['latency_sec']:.2f}s")
        except urllib.error.URLError as exc:
            print(f"warmup failed: {exc}")
            raise

    print("\n===== Benchmark =====")
    for prompt in DEFAULT_PROMPTS:
        for run_id in range(1, args.repeat + 1):
            result = chat_once(args, prompt)
            result["run_id"] = run_id
            results.append(result)
            print(
                f"{prompt[:18]}... run={run_id}, "
                f"latency={result['latency_sec']:.2f}s, "
                f"chars={result['content_chars']}, "
                f"tok/s={result['tokens_per_sec']}"
            )

    summary = {
        "count": len(results),
        "avg_latency_sec": average([item["latency_sec"] for item in results]),
        "avg_tokens_per_sec": average([item["tokens_per_sec"] for item in results]),
        "avg_content_chars": average([item["content_chars"] for item in results]),
    }

    output = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "model": args.model,
        "summary": summary,
        "results": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n===== Summary =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

