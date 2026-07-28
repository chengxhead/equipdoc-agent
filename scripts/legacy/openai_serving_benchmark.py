import argparse, asyncio, json, time, statistics, subprocess
from pathlib import Path

import httpx
from transformers import AutoTokenizer

SHORT_PROMPT = "轴承外圈故障一般有什么振动特征？请给出简洁维修建议。"

RAG_PROMPT = """你是机电装备智能运维诊断助手。请基于以下检索证据回答问题，不能编造设备编号、维修工单号、历史趋势和精确剩余寿命。

检索证据：
[1] 轴承外圈故障通常与外圈滚道局部剥落、点蚀、裂纹或安装座支撑刚度异常有关。滚动体经过缺陷位置时会产生周期性冲击。
[2] 外圈故障常表现为时域周期性冲击、包络谱中 BPFO 附近峰值增强、故障特征频率及倍频附近能量升高。
[3] 维修时应检查轴承座配合、润滑状态、外圈滚道磨损、异常温升和噪声。单段振动信号不能直接推断剩余寿命。

问题：如果模型诊断为轴承外圈故障，应该如何解释诊断依据并给出维修建议？
"""

def percentile(values, p):
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)

def gpu_mem_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
        )
        return max(int(x.strip()) for x in out.splitlines() if x.strip())
    except Exception:
        return None

async def sample_gpu(stop, samples):
    while not stop.is_set():
        mem = gpu_mem_mb()
        if mem is not None:
            samples.append(mem)
        await asyncio.sleep(0.2)

async def one_request(client, args, tokenizer, idx, prompt):
    url = args.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": True,
    }

    start = time.perf_counter()
    first_token_time = None
    text_parts = []

    async with client.stream("POST", url, json=payload, timeout=args.timeout) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj["choices"][0].get("delta", {}).get("content", "")
            except Exception:
                delta = ""
            if delta:
                if first_token_time is None:
                    first_token_time = time.perf_counter()
                text_parts.append(delta)

    end = time.perf_counter()
    output_text = "".join(text_parts)
    out_tokens = len(tokenizer.encode(output_text, add_special_tokens=False)) if output_text else 0

    return {
        "idx": idx,
        "latency_s": end - start,
        "ttft_s": (first_token_time - start) if first_token_time else None,
        "output_tokens": out_tokens,
        "decode_tps": out_tokens / max((end - (first_token_time or start)), 1e-6),
        "e2e_tps": out_tokens / max(end - start, 1e-6),
        "ok": True,
        "preview": output_text[:80],
    }

async def run(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
    prompt = RAG_PROMPT if args.prompt_mode == "rag" else SHORT_PROMPT

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        print("warmup...")
        await one_request(client, args, tokenizer, -1, prompt)

        stop = asyncio.Event()
        mem_samples = []
        sampler = asyncio.create_task(sample_gpu(stop, mem_samples))

        sem = asyncio.Semaphore(args.concurrency)
        started = time.perf_counter()

        async def guarded(i):
            async with sem:
                return await one_request(client, args, tokenizer, i, prompt)

        results = await asyncio.gather(*(guarded(i) for i in range(args.num_requests)))
        ended = time.perf_counter()

        stop.set()
        await sampler

    lat = [r["latency_s"] for r in results if r["ok"]]
    ttft = [r["ttft_s"] for r in results if r["ok"] and r["ttft_s"] is not None]
    out_tokens = [r["output_tokens"] for r in results if r["ok"]]
    decode_tps = [r["decode_tps"] for r in results if r["ok"]]
    total_output_tokens = sum(out_tokens)
    wall = ended - started

    summary = {
        "base_url": args.base_url,
        "model": args.model,
        "prompt_mode": args.prompt_mode,
        "concurrency": args.concurrency,
        "num_requests": args.num_requests,
        "max_tokens": args.max_tokens,
        "wall_time_s": wall,
        "success": len(results),
        "latency_avg_s": statistics.mean(lat),
        "latency_p50_s": percentile(lat, 50),
        "latency_p95_s": percentile(lat, 95),
        "ttft_avg_s": statistics.mean(ttft) if ttft else None,
        "ttft_p50_s": percentile(ttft, 50),
        "ttft_p95_s": percentile(ttft, 95),
        "output_tokens_avg": statistics.mean(out_tokens),
        "decode_tps_avg": statistics.mean(decode_tps),
        "throughput_output_tps": total_output_tokens / max(wall, 1e-6),
        "gpu_mem_peak_mb": max(mem_samples) if mem_samples else None,
        "gpu_mem_min_mb": min(mem_samples) if mem_samples else None,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base_url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--model_path", default="/root/autodl-tmp/models_llm/Qwen2.5-7B-Instruct-EquipDoc")
    p.add_argument("--prompt_mode", choices=["short", "rag"], default="rag")
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--num_requests", type=int, default=10)
    p.add_argument("--max_tokens", type=int, default=256)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    asyncio.run(run(args))

if __name__ == "__main__":
    main()