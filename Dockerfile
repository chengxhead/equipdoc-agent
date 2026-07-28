FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EQUIPDOC_DEMO_MODE=true \
    EQUIPDOC_SERVER_HOST=0.0.0.0 \
    EQUIPDOC_SERVER_PORT=7860

WORKDIR /app

COPY pyproject.toml README.md LICENSE NOTICE.md ./
COPY src ./src
COPY app_gradio.py ./
COPY data/samples ./data/samples
COPY data/knowledge ./data/knowledge
COPY data/knowledge_chunks.jsonl ./data/knowledge_chunks.jsonl

RUN pip install --no-cache-dir ".[demo]"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/runtime/uploads \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 7860

CMD ["python", "app_gradio.py"]

