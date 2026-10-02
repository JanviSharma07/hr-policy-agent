def tag_chunks(chunks: list[dict], document_id: int, title: str, version: str):
    ids, texts, metadatas = [], [], []
    for i, chunk in enumerate(chunks):
        ids.append(f"doc{document_id}_chunk{i}")
        # Section heading goes in front of the text so the embedding knows the context
        texts.append(f"{chunk['section']}\n{chunk['text']}")
        meta = {
            "document_id": document_id,
            "title": title,
            "version": version,
            "section": chunk["section"],
            "chunk_index": i,
        }
        if chunk["page"] is not None:  # ChromaDB metadata can't hold None
            meta["page"] = chunk["page"]
        metadatas.append(meta)
    return ids, texts, metadatas