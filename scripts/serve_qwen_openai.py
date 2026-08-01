from __future__ import annotations

import argparse
import os
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | None = Field(default="", max_length=32_768)


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1, max_length=64)
    temperature: float = 0.0
    top_p: float = 0.9
    max_tokens: int = Field(default=512, ge=1, le=2048)


def _is_loopback_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def validate_server_exposure(
    host: str,
    api_key: str,
    *,
    allow_unauthenticated_remote: bool = False,
) -> None:
    if _is_loopback_host(host) or api_key.strip() not in {"", "EMPTY"}:
        return
    if allow_unauthenticated_remote:
        return
    raise ValueError(
        "Refusing to expose an unauthenticated model service on a non-loopback host. "
        "Set --api-key or explicitly pass --allow-unauthenticated-remote."
    )


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Serve a local Qwen model with a minimal OpenAI API.")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--served-model-name", default="qwen-equipdoc")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dtype", choices=["auto", "float16", "bfloat16"], default="auto")
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-concurrent-requests", type=int, default=1)
    parser.add_argument("--api-key", default=os.getenv("EQUIPDOC_LLM_API_KEY", "EMPTY"))
    parser.add_argument("--allow-unauthenticated-remote", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    try:
        validate_server_exposure(
            args.host,
            args.api_key,
            allow_unauthenticated_remote=args.allow_unauthenticated_remote,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.max_concurrent_requests < 1:
        raise SystemExit("--max-concurrent-requests must be at least 1")
    try:
        import torch
        import uvicorn
        from fastapi import Depends, FastAPI, Header, HTTPException
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
    model_path = args.model_path.resolve(strict=True)
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
    inference_slots = threading.BoundedSemaphore(args.max_concurrent_requests)
    api_key = args.api_key.strip()
    auth_required = api_key not in {"", "EMPTY"}

    def require_api_key(authorization: str | None = Header(default=None)) -> None:
        if not auth_required:
            return
        expected = f"Bearer {api_key}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Invalid bearer token")

    @app.get("/healthz", dependencies=[Depends(require_api_key)])
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

    @app.get("/v1/models", dependencies=[Depends(require_api_key)])
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

    @app.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
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
        if not inference_slots.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="Model is processing another request")
        try:
            with torch.inference_mode():
                output_ids = model.generate(**inputs, **generation_args)
        finally:
            inference_slots.release()
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

    if auth_required:
        auth_label = "bearer token required"
    elif _is_loopback_host(args.host):
        auth_label = "loopback-only without auth"
    else:
        auth_label = "unauthenticated remote access explicitly enabled"
    print(f"Model ready: http://{args.host}:{args.port}/v1 ({auth_label})", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
