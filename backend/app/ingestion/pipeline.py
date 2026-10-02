from pathlib import Path
from app.ingestion.reader import read_document
from app.ingestion.chunker import chunk_blocks
from app.ingestion.tagger import tag_chunks


def prepare_document(path: Path, document_id: int, title: str, version: str):
    chunks = chunk_blocks(read_document(path))
    if not chunks:
        raise ValueError("No text found. The file may be a scanned image.")
    return tag_chunks(chunks, document_id, title, version)