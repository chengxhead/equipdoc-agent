import argparse
import json
import os
import time
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Load a HuggingFace causal LM with bitsandbytes 4-bit and benchmark memory/latency.")
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--prompt", default="轴承外圈故障一般有什么振动特征？")
    parser.add_argument("--max_new_tokens", type=int, default=256)
    parser.add_argument("--output", default="bnb_4bit_memory_benchmark.json")
    return parser.parse_args()


def format_bytes(num_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024


def cuda_memory_snapshot(torch):
    if not torch.cuda.is_available():
        return {}
    return {
        "allocated_bytes": torch.cuda.memory_allocated(),
        "reserved_bytes": torch.cuda.memory_reserved(),
        "max_allocated_bytes": torch.cuda.max_memory_allocated(),
        "allocated_human": format_bytes(torch.cuda.memory_allocated()),
        "reserved_human": format_bytes(torch.cuda.memory_reserved()),
        "max_allocated_human": format_bytes(torch.cuda.max_memory_allocated()),
    }


def main():
    args = parse_args()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except Exception as exc:
        raise RuntimeError(
            "Missing torch/transformers. Please run this in the same environment used by Qwen-EquipDoc."
        ) from exc

    try:
        import bitsandbytes  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "bitsandbytes is not available. Do not install it in the working environment if you are worried "
            "about breaking CUDA/Torch. Prefer creating a cloned conda env for this benchmark."
        ) from exc

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    started_load = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        quantization_config=quant_config,
        device_map="auto",
        trust_remote_code=True,
    )
    load_sec = time.perf_counter() - started_load

    after_load_memory = cuda_memory_snapshot(torch)

    messages = [{"role": "user", "content": args.prompt}]
    if hasattr(tokenizer, "apply_chat_template"):
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        text = args.prompt

    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    if torch.cuda.is_available():
        torch.cuda.synchronize()
    started_generate = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
        )
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    generate_sec = time.perf_counter() - started_generate

    new_tokens = int(output_ids.shape[-1] - inputs["input_ids"].shape[-1])
    response = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)

    after_generate_memory = cuda_memory_snapshot(torch)
    output = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model_path": os.path.abspath(args.model_path),
        "quantization": "bitsandbytes_4bit_nf4_double_quant",
        "load_sec": load_sec,
        "generate_sec": generate_sec,
        "new_tokens": new_tokens,
        "tokens_per_sec": new_tokens / generate_sec if generate_sec > 0 else None,
        "after_load_memory": after_load_memory,
        "after_generate_memory": after_generate_memory,
        "prompt": args.prompt,
        "response_preview": response[:500],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("===== bitsandbytes 4-bit Benchmark =====")
    print(f"model_path: {output['model_path']}")
    print(f"load_sec: {load_sec:.2f}")
    print(f"generate_sec: {generate_sec:.2f}")
    print(f"new_tokens: {new_tokens}")
    print(f"tokens_per_sec: {output['tokens_per_sec']:.2f}" if output["tokens_per_sec"] else "tokens_per_sec: N/A")
    print(f"after_load_memory: {after_load_memory}")
    print(f"after_generate_memory: {after_generate_memory}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

