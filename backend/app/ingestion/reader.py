from collections import Counter
from pathlib import Path
import pymupdf
from docx import Document as DocxDocument
from docx.table import Table

DEFAULT_SECTION = "General"


def _is_heading(text: str, bold: bool, size: float, body_size: float) -> bool:
    if not text or len(text) > 90 or len(text.split()) > 12:
        return False
    if size >= body_size * 1.15:
        return True
    return bold and not text.endswith(".")


def read_pdf(path: Path) -> list[dict]:
    lines = []
    with pymupdf.open(path) as pdf:
        for page_no, page in enumerate(pdf, start=1):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:  # skip images
                    continue
                for line in block["lines"]:
                    spans = [s for s in line["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    text = " ".join(s["text"].strip() for s in spans)
                    size = max(s["size"] for s in spans)
                    bold = all((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
                    lines.append((page_no, text, size, bold))

    sizes = Counter(round(size) for _, _, size, _ in lines)
    body_size = sizes.most_common(1)[0][0] if sizes else 11

    blocks, section = [], DEFAULT_SECTION
    for page_no, text, size, bold in lines:
        if _is_heading(text, bold, size, body_size):
            section = text
            continue
        last = blocks[-1] if blocks else None
        if last and last["page"] == page_no and last["section"] == section:
            last["text"] += " " + text
        else:
            blocks.append({"text": text, "page": page_no, "section": section})
    return blocks


def read_docx(path: Path) -> list[dict]:
    doc = DocxDocument(path)
    blocks, section = [], DEFAULT_SECTION
    for item in doc.iter_inner_content():
        if isinstance(item, Table):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in item.rows]
            text = "\n".join(r for r in rows if r.strip(" |"))
        else:
            text = item.text.strip()
            style = (item.style.name or "").lower() if item.style else ""
            if text and (style.startswith("heading") or style == "title"):
                section = text
                continue
        if text:
            blocks.append({"text": text, "page": None, "section": section})
    return blocks


def read_document(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".docx":
        return read_docx(path)
    raise ValueError(f"Unsupported file type: {suffix}")