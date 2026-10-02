import shutil
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.config import UPLOAD_DIR
from app.db.database import get_db
from app.db.models import Document, User, utcnow
from app.auth.dependencies import require_hr_admin
from app.ingestion.pipeline import prepare_document
from app.retrieval.embeddings import embed_texts
from app.retrieval.vector_store import add_chunks, delete_document_chunks, get_document_chunks

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED = {".pdf", ".docx"}


def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


def _serialize(d: Document) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "version": d.version,
        "chunk_count": d.chunk_count,
        "uploaded_at": d.uploaded_at,
    }


def _get_or_404(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("")
def list_documents(db: Session = Depends(get_db), admin: User = Depends(require_hr_admin)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [_serialize(d) for d in docs]


@router.post("")
def upload_document(
    title: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_hr_admin),
):
    path = _save_upload(file)
    doc = Document(title=title, filename=path.name, version=version, uploaded_by=admin.id)
    db.add(doc)
    db.flush()  # gives us doc.id without saving yet
    doc_id = doc.id

    try:
        ids, texts, metas = prepare_document(path, doc_id, title, version)
        add_chunks(ids, texts, metas)
        doc.chunk_count = len(ids)
        db.commit()
    except Exception as e:
        db.rollback()
        delete_document_chunks(doc_id)  # never leave vectors without a registry row
        path.unlink(missing_ok=True)
        code = 400 if isinstance(e, ValueError) else 500
        raise HTTPException(status_code=code, detail=f"Ingestion failed: {e}")

    db.refresh(doc)
    return _serialize(doc)


@router.put("/{document_id}")
def replace_document(
    document_id: int,
    version: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_hr_admin),
):
    doc = _get_or_404(db, document_id)
    new_path = _save_upload(file)

    # Prepare and embed the new version BEFORE touching the old one,
    # so a failure here leaves the old policy fully intact.
    try:
        ids, texts, metas = prepare_document(new_path, doc.id, doc.title, version)
        vectors = embed_texts(texts)
    except Exception as e:
        new_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {e}")

    delete_document_chunks(doc.id)
    add_chunks(ids, texts, metas, embeddings=vectors)

    old_path = UPLOAD_DIR / doc.filename
    doc.filename, doc.version = new_path.name, version
    doc.chunk_count, doc.uploaded_at = len(ids), utcnow()
    db.commit()
    old_path.unlink(missing_ok=True)

    db.refresh(doc)
    return _serialize(doc)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_hr_admin),
):
    doc = _get_or_404(db, document_id)

    # Vectors first. If this fails, the row survives and HR can retry,
    # so the system can never answer from a policy that "doesn't exist".
    delete_document_chunks(doc.id)

    path = UPLOAD_DIR / doc.filename
    db.delete(doc)
    db.commit()
    path.unlink(missing_ok=True)
    return {"deleted": document_id}


@router.get("/{document_id}/chunks")
def preview_chunks(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_hr_admin),
):
    _get_or_404(db, document_id)
    return [
        {"chunk_index": m["chunk_index"], "page": m.get("page"), "section": m["section"], "text": t}
        for t, m in get_document_chunks(document_id)
    ]