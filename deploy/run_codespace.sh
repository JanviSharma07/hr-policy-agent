#!/usr/bin/env bash
# Runs the full app (frontend + backend + all models) inside a GitHub Codespace.
# Usage, from the project folder in the Codespace terminal:
#     bash deploy/run_codespace.sh
# Then: Ports tab -> port 8000 -> right-click -> Port Visibility -> Public, and share that link.
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)

# 1. Python packages (only the first time; CPU-only PyTorch is much smaller)
if ! python -c "import sentence_transformers, fastapi, chromadb, langgraph" 2>/dev/null; then
  echo "== Installing Python packages (first time only, about 5 minutes) =="
  pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
  pip install --quiet -r backend/requirements.txt
fi

# 2. Build the React app (only the first time, or after frontend changes)
if [ ! -f frontend/dist/index.html ]; then
  echo "== Building the frontend =="
  cd frontend
  npm ci --silent
  echo "VITE_API_BASE_URL=" > .env.production.local   # call the backend on the same address
  npm run build
  cd "$ROOT"
fi

# 3. Secrets: from Codespaces secrets if set, otherwise asked once
if [ -z "$GEMINI_API_KEY" ]; then
  read -r -s -p "Paste your Gemini API key and press Enter: " GEMINI_API_KEY; echo
fi
export GEMINI_API_KEY
export JWT_SECRET=${JWT_SECRET:-$(python -c "import secrets; print(secrets.token_hex(32))")}

# 4. Demo settings: built-in database with the test accounts and sample policies
mkdir -p backend/data
export DATABASE_URL="sqlite:///$ROOT/backend/data/app.db"
export SEED_DEMO=1 SERVE_FRONTEND=1
export GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.5-flash}
export GEMINI_FAST_MODEL=${GEMINI_FAST_MODEL:-gemini-3.5-flash-lite}
export GEMINI_FALLBACK_MODELS=${GEMINI_FALLBACK_MODELS:-gemini-3.5-flash-lite,gemini-3.8-flash}

if [ -f backend/models/router/config.json ]; then
  echo "== Router: your fine-tuned DistilBERT =="
else
  echo "== Router: DistilBERT not found in backend/models/router, using the Gemini router =="
fi
echo "== Starting. When you see 'Application startup complete', open the Ports tab =="
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
