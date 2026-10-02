MAX_WORDS = 250      # roughly 330 tokens, safely under the model's 512 limit
OVERLAP_WORDS = 40   # only used when a single section is too long


def _make(words: list[str], page, section: str) -> dict:
    return {"text": " ".join(words), "page": page, "section": section}


def _windows(words: list[str]):
    step = MAX_WORDS - OVERLAP_WORDS
    for start in range(0, len(words), step):
        yield words[start:start + MAX_WORDS]
        if start + MAX_WORDS >= len(words):
            break


def chunk_blocks(blocks: list[dict]) -> list[dict]:
    chunks = []
    buf, page, section = [], None, None

    for block in blocks:
        words = block["text"].split()
        new_section = block["section"] != section
        too_big = len(buf) + len(words) > MAX_WORDS

        if buf and (new_section or too_big):
            chunks.append(_make(buf, page, section))
            buf = []
        if not buf:
            page, section = block["page"], block["section"]

        if len(words) > MAX_WORDS:
            chunks.extend(_make(w, block["page"], block["section"]) for w in _windows(words))
            continue
        buf.extend(words)

    if buf:
        chunks.append(_make(buf, page, section))
    return chunks