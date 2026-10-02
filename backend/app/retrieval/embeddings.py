from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL


@lru_cache
def get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = get_model().encode(texts, normalize_embeddings=True, batch_size=32)
    return vectors.tolist()