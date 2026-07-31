from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(project_root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(project_root / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve(project_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    demo_mode: bool
    agentic_mode: bool
    agent_max_steps: int
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    llm_timeout_seconds: float
    bearing_model_path: Path
    bearing_norm_path: Path
    sample_root: Path
    upload_root: Path
    max_upload_bytes: int
    rag_enabled: bool
    rag_chunks_path: Path
    rag_db_dir: Path
    rag_collection: str
    embedding_model: str
    rag_top_k: int
    server_host: str
    server_port: int
    gradio_share: bool

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        root = (project_root or PROJECT_ROOT).resolve()
        _load_dotenv(root)
        max_upload_mb = max(1, int(os.getenv("EQUIPDOC_MAX_UPLOAD_MB", "8")))
        return cls(
            project_root=root,
            demo_mode=_env_bool("EQUIPDOC_DEMO_MODE", True),
            agentic_mode=_env_bool("EQUIPDOC_AGENTIC_MODE", False),
            agent_max_steps=max(1, min(4, int(os.getenv("EQUIPDOC_AGENT_MAX_STEPS", "3")))),
            llm_base_url=os.getenv("EQUIPDOC_LLM_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/"),
            llm_model=os.getenv("EQUIPDOC_LLM_MODEL", "qwen-equipdoc"),
            llm_api_key=os.getenv("EQUIPDOC_LLM_API_KEY", "EMPTY"),
            llm_timeout_seconds=float(os.getenv("EQUIPDOC_LLM_TIMEOUT_SECONDS", "120")),
            bearing_model_path=_resolve(root, os.getenv("EQUIPDOC_BEARING_MODEL_PATH", "models/bearing_cnn.pth")),
            bearing_norm_path=_resolve(root, os.getenv("EQUIPDOC_BEARING_NORM_PATH", "data/processed/norm.npy")),
            sample_root=_resolve(root, os.getenv("EQUIPDOC_SAMPLE_ROOT", "data/samples")),
            upload_root=_resolve(root, os.getenv("EQUIPDOC_UPLOAD_ROOT", "runtime/uploads")),
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            rag_enabled=_env_bool("EQUIPDOC_RAG_ENABLED", True),
            rag_chunks_path=_resolve(root, os.getenv("EQUIPDOC_RAG_CHUNKS_PATH", "data/knowledge_chunks.jsonl")),
            rag_db_dir=_resolve(root, os.getenv("EQUIPDOC_RAG_DB_DIR", "vector_db/chroma_equipdoc")),
            rag_collection=os.getenv("EQUIPDOC_RAG_COLLECTION", "equipdoc_rag"),
            embedding_model=os.getenv("EQUIPDOC_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            rag_top_k=max(1, int(os.getenv("EQUIPDOC_RAG_TOP_K", "5"))),
            server_host=os.getenv("EQUIPDOC_SERVER_HOST", "0.0.0.0"),
            server_port=int(os.getenv("EQUIPDOC_SERVER_PORT", "7860")),
            gradio_share=_env_bool("EQUIPDOC_GRADIO_SHARE", False),
        )

    def ensure_runtime_dirs(self) -> None:
        self.upload_root.mkdir(parents=True, exist_ok=True)

    @property
    def mode_name(self) -> str:
        if self.demo_mode:
            return "demo"
        return "full_agentic" if self.agentic_mode else "full"
