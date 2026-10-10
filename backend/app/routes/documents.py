import shutil
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.config import UPLOAD_DIR
from app.db.database import get_db
from app.db.models import Document, User
from app.auth.dependencies import require_hr_admin
from app.ingestion.pipeline import prepare_document
from app.retrieval.vector_store import (
    add_chunks, delete_document_chunks, get_document_chunks, sync_document_chunks,
)

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
        "family_id": d.family_id,
        "title": d.title,
        "version": d.version,
        "status": "current" if d.is_active else "archived",
        "chunk_count": d.chunk_count,
        "uploaded_at": d.uploaded_at,
    }


def _get_or_404(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _ingest(db: Session, doc: Document, path: Path) -> None:
    """Chunk, embed and store one version. Cleans up after itself if anything fails."""
    doc_id = doc.id
    try:
        ids, texts, metas = prepare_document(path, doc.id, doc.family_id, doc.title, doc.version)
        add_chunks(ids, texts, metas)
        doc.chunk_count = len(ids)
    except Exception as e:
        db.rollback()
        delete_document_chunks(doc_id)  # never leave vectors without a registry row
        path.unlink(missing_ok=True)
        code = 400 if isinstance(e, ValueError) else 500
        raise HTTPException(status_code=code, detail=f"Ingestion failed: {e}")


@router.get("")
def list_documents(db: Session = Depends(get_db), admin: User = Depends(require_hr_admin)):
    docs = (db.query(Document)
            .order_by(Document.family_id, Document.uploaded_at.desc()).all())
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
    doc = Document(title=title, filename=path.name, version=version,
                   uploaded_by=admin.id, is_active=True)
    db.add(doc)
    db.flush()               # gives us doc.id without saving yet
    doc.family_id = doc.id   # a new policy starts its own family

    _ingest(db, doc, path)
    db.commit()
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
    """Upload a new version. The old version is archived, not deleted,
    so the comparison agent can still read it."""
    old = _get_or_404(db, document_id)
    if not old.is_active:
        raise HTTPException(status_code=400, detail="This version is archived. Replace the current version instead.")
    taken = {d.version for d in db.query(Document).filter(Document.family_id == old.family_id)}
    if version in taken:
        raise HTTPException(status_code=400, detail=f"Version {version} already exists for this policy")

    path = _save_upload(file)
    new = Document(title=old.title, filename=path.name, version=version,
                   uploaded_by=admin.id, family_id=old.family_id, is_active=True)
    db.add(new)
    db.flush()

    _ingest(db, new, path)
    old.is_active = False
    db.commit()

    # Mark the old version's chunks as archived so normal search skips them.
    # (If this ever fails, the startup sync in main.py repairs it.)
    sync_document_chunks(old.id, old.family_id, False)

    db.refresh(new)
    return _serialize(new)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_hr_admin),
):
    """Deletes the whole policy: every version, its chunks and its files."""
    doc = _get_or_404(db, document_id)
    versions = db.query(Document).filter(Document.family_id == doc.family_id).all()

    # Vectors first. If this fails, the rows survive and HR can retry,
    # so the system can never answer from a policy that "doesn't exist".
    for v in versions:
        delete_document_chunks(v.id)

    paths = [UPLOAD_DIR / v.filename for v in versions]
    for v in versions:
        db.delete(v)
    db.commit()
    for p in paths:
        p.unlink(missing_ok=True)
    return {"deleted_versions": [v.id for v in versions]}


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
