from app.config import TOP_K_RETRIEVE, TOP_K_FINAL, MIN_RELEVANCE, RELATIVE_KEEP
from app.retrieval.embeddings import embed_query
from app.retrieval.vector_store import query_chunks
from app.retrieval.reranker import rerank


def search(
    question: str,
    top_k: int = TOP_K_FINAL,
    use_reranker: bool = True,
    min_relevance: float = MIN_RELEVANCE,
    include_archived: bool = False,
    relative_keep: float = RELATIVE_KEEP,
) -> list[dict]:
    candidates = query_chunks(embed_query(question), TOP_K_RETRIEVE, include_archived=include_archived)
    if not use_reranker:
        return candidates[:top_k]

    ranked = rerank(question, candidates, top_k)

    if min_relevance <= 0:           # evaluation mode: return all top_k
        return ranked
    if not ranked or ranked[0]["relevance"] < min_relevance:
        return []                    # nothing in the policies matches
    if relative_keep <= 0:           # agent mode: the best match is relevant, so read all top_k
        return ranked
    cutoff = max(min_relevance, ranked[0]["relevance"] * relative_keep)
    return [r for r in ranked if r["relevance"] >= cutoff]


def to_citation(result: dict) -> dict:
    m = result["metadata"]
    return {
        "document_id": m["document_id"],
        "title": m["title"],
        "version": m["version"],
        "status": "current" if m.get("is_active", True) else "archived",
        "section": m["section"],
        "page": m.get("page"),  # None for DOCX files
    }
