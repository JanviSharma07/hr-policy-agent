import math
from functools import lru_cache
from sentence_transformers import CrossEncoder
from app.config import RERANKER_MODEL, RERANKER_DIR


@lru_cache
def get_reranker() -> CrossEncoder:
    if (RERANKER_DIR / "config.json").exists():
        return CrossEncoder(str(RERANKER_DIR))
    return CrossEncoder(RERANKER_MODEL)


def rerank(question: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return []
    pairs = [(question, c["text"]) for c in candidates]
    scores = get_reranker().predict(pairs)
    for c, score in zip(candidates, scores):
        c["rerank_score"] = float(score)
        c["relevance"] = 1 / (1 + math.exp(-float(score)))  # sigmoid: score -> 0..1
    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_k]