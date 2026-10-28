import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine, SessionLocal
from app.db import models  # noqa: F401  (registers the tables)
from app.db.migrate import run_migrations
from app.retrieval.vector_store import sync_document_chunks
from app.routes import auth, documents, search, chat
from app.seed import seed_demo

# --- Startup: tables, new columns, and ChromaDB kept in step with PostgreSQL ---
Base.metadata.create_all(bind=engine)
run_migrations(engine)
with SessionLocal() as db:
    for doc in db.query(models.Document).all():
        sync_document_chunks(doc.id, doc.family_id, doc.is_active)
    seed_demo(db)  # hosted demo only (SEED_DEMO=1): test accounts + sample policies

# Load the embedding and reranker models now, so the first question isn't slow
from app.retrieval.embeddings import get_model  # noqa: E402
from app.retrieval.reranker import get_reranker  # noqa: E402
from app.agent.router import _distilbert  # noqa: E402
get_model()
get_reranker()
_distilbert()  # the router too, so the first question doesn't wait for it

app = FastAPI(title="HR Policy Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",  # React (Vite) dev server
                   *[o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Hosted version: the built React app is served from the same address as the API
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if os.getenv("SERVE_FRONTEND") == "1" and FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
