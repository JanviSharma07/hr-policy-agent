from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine, SessionLocal
from app.db import models  # noqa: F401  (registers the tables)
from app.db.migrate import run_migrations
from app.retrieval.vector_store import sync_document_chunks
from app.routes import auth, documents, search, chat

# --- Startup: tables, new columns, and ChromaDB kept in step with PostgreSQL ---
Base.metadata.create_all(bind=engine)
run_migrations(engine)
with SessionLocal() as db:
    for doc in db.query(models.Document).all():
        sync_document_chunks(doc.id, doc.family_id, doc.is_active)

app = FastAPI(title="HR Policy Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React (Vite) dev server
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
