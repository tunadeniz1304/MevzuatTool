# MevzuatTool retrieval servisi — torch'suz, ONNX Runtime int8 (ADR-0016/0018)
# Modeller (models/onnx) ve korpus (data/kanun/korpus.jsonl) imaja GÖMÜLMEZ → read-only volume.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_NO_ADVISORY_WARNINGS=1 \
    EMBED_BACKEND=onnx-int8 \
    MODEL_DIR=/app/models/onnx \
    KORPUS_YOL=/app/data/kanun/korpus.jsonl \
    ORT_THREADS=4

WORKDIR /app
COPY requirements-servis.txt .
RUN pip install -r requirements-servis.txt

# non-root kullanıcı
RUN useradd --create-home --uid 10001 mevzuat
COPY --chown=mevzuat:mevzuat src/ src/
COPY --chown=mevzuat:mevzuat scripts/kanun/retrieval/ingest_qdrant.py scripts/kanun/retrieval/ingest_qdrant.py
USER mevzuat

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "kanun.api.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
