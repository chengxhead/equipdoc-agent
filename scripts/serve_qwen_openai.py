from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str | None = ""


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float = 0.0
    top_p: float = 0.9
    max_tokens: int = Field(default=512, ge=1, le=2048)


def parse_args():
    parser = argparse.ArgumentParser(description="Serve a local Qwen model with a minimal OpenAI API.")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--served-model-name", default="qwen-equipdoc")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dtype", choices=["auto", "float16", "bfloat16"], default="auto")
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import torch
        import uvicorn
        from fastapi import FastAPI, HTTPException
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Install torch, transformers, accelerate, fastapi and uvicorn in the AutoDL environment."
        ) from exc

    dtype = {
        "auto": "auto",
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[args.dtype]
    model_path = args.model_path.resolve()
    print(f"Loading tokenizer from: {model_path.name}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    print(f"Loading model: {args.served_model_name}", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    app = FastAPI(title="EquipDoc local Qwen service")

    @app.get("/healthz")
    def healthz():
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        return {
            "ready": True,
            "model": args.served_model_name,
            "model_directory": model_path.name,
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "gpu_name": gpu_name,
        }

    @app.get("/v1/models")
    def list_models():
        return {
            "object": "list",
            "data": [
                {
                    "id": args.served_model_name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatRequest):
        if request.model != args.served_model_name:
            raise HTTPException(status_code=404, detail=f"Unknown model: {request.model}")
        messages = [
            {"role": message.role, "content": message.content or ""}
            for message in request.messages
        ]
        rendered = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer([rendered], return_tensors="pt").to(model.device)
        prompt_tokens = int(inputs["input_ids"].shape[-1])
        if prompt_tokens > args.max_input_tokens:
            raise HTTPException(
                status_code=400,
                detail=f"Prompt has {prompt_tokens} tokens; limit is {args.max_input_tokens}.",
            )
        generation_args = {
            "max_new_tokens": request.max_tokens,
            "do_sample": request.temperature > 0,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if request.temperature > 0:
            generation_args.update(temperature=request.temperature, top_p=request.top_p)
        with torch.inference_mode():
            output_ids = model.generate(**inputs, **generation_args)
        new_ids = output_ids[0][prompt_tokens:]
        completion_tokens = int(new_ids.shape[-1])
        content = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": args.served_model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    print(f"Model ready: http://{args.host}:{args.port}/v1", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
