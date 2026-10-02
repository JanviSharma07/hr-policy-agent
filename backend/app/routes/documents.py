from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Document, User
from app.auth.dependencies import require_hr_admin

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
def list_documents(db: Session = Depends(get_db), admin: User = Depends(require_hr_admin)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "filename": d.filename,
            "version": d.version,
            "chunk_count": d.chunk_count,
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]