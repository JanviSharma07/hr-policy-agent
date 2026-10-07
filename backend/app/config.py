import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # one working day

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # the backend folder
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "hr_policies"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"   # pretrained placeholder
RERANKER_DIR = BASE_DIR / "models" / "reranker"            # fine-tuned weights go here later
TOP_K_RETRIEVE = 20
TOP_K_FINAL = 5
MIN_RELEVANCE = 0.05   # floor: if the best result is below this, nothing is relevant
RELATIVE_KEEP = 0.5    # keep results with at least half the best result's relevance