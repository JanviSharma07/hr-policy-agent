# Hosted demo: React frontend + FastAPI backend in one container (Hugging Face Spaces).
# Local development is unchanged: this file is only used by the Space.

# ---- 1. Build the React app ----
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Empty API address = call the backend on the same address the page came from
RUN echo "VITE_API_BASE_URL=" > .env.production.local && npm run build

# ---- 2. Python backend ----
FROM python:3.12-slim
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /app

# CPU-only PyTorch keeps the image small (no GPU on the free tier)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=user backend/ backend/
COPY --from=frontend --chown=user /frontend/dist frontend/dist
RUN chown user /app
USER user

# Download the embedding and reranker models into the image, so start-up is quick
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# GEMINI_API_KEY and JWT_SECRET come from the Space's secrets, never from files
ENV DATABASE_URL=sqlite:////app/backend/data/app.db \
    SEED_DEMO=1 \
    SERVE_FRONTEND=1 \
    GEMINI_MODEL=gemini-3.5-flash \
    GEMINI_FAST_MODEL=gemini-3.5-flash-lite \
    GEMINI_FALLBACK_MODELS=gemini-3.5-flash-lite,gemini-3.8-flash
RUN mkdir -p backend/data

WORKDIR /app/backend
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
