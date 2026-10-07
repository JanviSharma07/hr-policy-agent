from functools import lru_cache
import chromadb
from app.config import CHROMA_DIR, COLLECTION_NAME
from app.retrieval.embeddings import embed_texts


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

def query_chunks(query_vector: list[float], n: int) -> list[dict]:
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    res = collection.query(
        query_embeddings=[query_vector],
        n_results=min(n, total),
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