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