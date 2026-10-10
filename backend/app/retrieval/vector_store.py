from functools import lru_cache
import chromadb
from app.config import CHROMA_DIR, COLLECTION_NAME
from app.retrieval.embeddings import embed_texts

MAX_FAMILY_CHUNKS = 60  # cap for summarising / comparing a whole policy


@lru_cache
def get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(COLLECTION_NAME)


def add_chunks(ids, texts, metadatas, embeddings=None):
    if not ids:
        return
    if embeddings is None:
        embeddings = embed_texts(texts)
    get_collection().add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def delete_document_chunks(document_id: int):
    get_collection().delete(where={"document_id": document_id})


def get_document_chunks(document_id: int):
    res = get_collection().get(where={"document_id": document_id}, include=["documents", "metadatas"])
    pairs = zip(res["documents"], res["metadatas"])
    return sorted(pairs, key=lambda p: p[1]["chunk_index"])


def sync_document_chunks(document_id: int, family_id: int, is_active: bool):
    """Make the chunks' family_id / is_active match the database row."""
    collection = get_collection()
    res = collection.get(where={"document_id": document_id}, include=["metadatas"])
    ids, metas = [], []
    for chunk_id, meta in zip(res["ids"], res["metadatas"]):
        if meta.get("family_id") != family_id or meta.get("is_active") != is_active:
            ids.append(chunk_id)
            metas.append({**meta, "family_id": family_id, "is_active": is_active})
    if ids:
        collection.update(ids=ids, metadatas=metas)


def query_chunks(query_vector: list[float], n: int, include_archived: bool = False) -> list[dict]:
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    res = collection.query(
        query_embeddings=[query_vector],
        n_results=min(n, total),
        where=None if include_archived else {"is_active": True},
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for chunk_id, text, meta, dist in zip(
        res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        results.append({
            "id": chunk_id,
            "text": text,
            "metadata": meta,
            "vector_score": 1 - dist / 2,  # converts ChromaDB distance to cosine similarity
        })
    return results


def get_family_chunks(family_id: int, active_only: bool = True) -> list[dict]:
    """Every chunk of one policy (all versions, or only the current one), in reading order."""
    where = {"family_id": family_id}
    if active_only:
        where = {"$and": [{"family_id": family_id}, {"is_active": True}]}
    res = get_collection().get(where=where, include=["documents", "metadatas"])
    chunks = [
        {"id": i, "text": t, "metadata": m}
        for i, t, m in zip(res["ids"], res["documents"], res["metadatas"])
    ]
    chunks.sort(key=lambda c: (c["metadata"]["document_id"], c["metadata"]["chunk_index"]))
    return chunks[:MAX_FAMILY_CHUNKS]
