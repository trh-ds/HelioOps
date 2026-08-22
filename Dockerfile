# Hugging Face Spaces builds THIS file, at the repo root — deployment/Dockerfile.backend
# is not picked up (different name, different path). Keep the two in step.
#
# Space: SDK=Docker, hardware CPU basic (free, 2 vCPU / 16 GB). See
# docs/HOW_TO_DEPLOY_BACKEND.md for secrets and verification.
FROM python:3.12-slim

# Spaces runs the container as UID 1000. Everything below assumes that user.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONPATH=/home/user/app \
    PYTHONUNBUFFERED=1 \
    PORT=7860
WORKDIR $HOME/app

COPY --chown=user backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --chown=user is load-bearing, not style: ChromaDB opens chroma.sqlite3
# read-write (sqlite WAL). Without it UID 1000 cannot write the WAL, Chroma
# raises, retrieve_chunks() swallows it and every advisory is silently
# ungrounded. /health/ready's knowledge_base check is what catches this.
COPY --chown=user backend/ backend/

# Bake the embedder AFTER `USER user`. As root it caches to /root/.cache, which
# UID 1000 cannot read at runtime -> a silent ~90s re-download on first request.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
