from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.config import MIN_RELEVANCE
from app.db.models import User
from app.retrieval.search import search, to_citation

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search_route(
    q: str,
    use_reranker: bool = True,
    min_relevance: float = MIN_RELEVANCE,
    user: User = Depends(get_current_user),
):
    results = search(q, use_reranker=use_reranker, min_relevance=min_relevance)
    return [
        {
            **to_citation(r),
            "relevance": round(r["relevance"], 3) if "relevance" in r else None,
            "vector_score": round(r["vector_score"], 3),
            "text": r["text"],
        }
        for r in results
    ]