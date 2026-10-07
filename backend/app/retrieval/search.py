from app.config import TOP_K_RETRIEVE, TOP_K_FINAL, MIN_RELEVANCE, RELATIVE_KEEP
from app.retrieval.embeddings import embed_query
from app.retrieval.vector_store import query_chunks
from app.retrieval.reranker import rerank


def search(
    question: str,
    top_k: int = TOP_K_FINAL,
    use_reranker: bool = True,
    min_relevance: float = MIN_RELEVANCE,
) -> list[dict]:
    candidates = query_chunks(embed_query(question), TOP_K_RETRIEVE)
    if not use_reranker:
        return candidates[:top_k]

    ranked = rerank(question, candidates, top_k)

    if min_relevance <= 0:           # evaluation mode: return all top_k
        return ranked
    if not ranked or ranked[0]["relevance"] < min_relevance:
        return []                    # nothing in the policies matches
    cutoff = max(min_relevance, ranked[0]["relevance"] * RELATIVE_KEEP)
    return [r for r in ranked if r["relevance"] >= cutoff]


def to_citation(result: dict) -> dict:
    m = result["metadata"]
    return {
        "document_id": m["document_id"],
        "title": m["title"],
        "version": m["version"],
        "section": m["section"],
        "page": m.get("page"),  # None for DOCX files
    }