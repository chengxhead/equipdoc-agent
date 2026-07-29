# Model artifacts

Large model weights are intentionally excluded from Git.

Full mode expects, by default:

- `models/bearing_cnn.pth`: the small 1D CNN state dictionary.
- An OpenAI-compatible Qwen service configured through `.env`.

The reproducible local service entry point is `scripts/serve_qwen_openai.py`; the AutoDL quality and latency procedure is documented in `docs/p2-autodl-full-evaluation.md`.

The 14 GB merged Qwen model should stay on AutoDL or a model hosting service. A later release should add a model card, LoRA training configuration, sanitized sample data, and the exact base-model revision instead of committing the merged model to GitHub.
