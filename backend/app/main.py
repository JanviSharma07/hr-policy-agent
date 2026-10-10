from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import Base, engine
from app.db import models  # noqa: F401  (registers the tables)
from app.routes import auth, documents, search, chat
Base.metadata.create_all(bind=engine)

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
