"""HR Inbox. Employees send private questions to HR, and questions Humanly couldn't answer
arrive here automatically. HR replies; a reply can also be taught to Humanly so the AI
answers the same question itself next time (the reply becomes a chunk in ChromaDB)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Document, HRRequest, User
from app.auth.dependencies import get_current_user, require_hr_admin

router = APIRouter(prefix="/requests", tags=["hr requests"])

TOPICS = ["Salary & payroll", "Personal or medical", "Workplace concern", "Leave & attendance", "Other"]
HR_ANSWERS_TITLE = "HR Answers"


class NewRequest(BaseModel):
    topic: str | None = None
    question: str


class Reply(BaseModel):
    reply: str
    teach: bool = False  # also add this answer to Humanly's knowledge


def _out(r: HRRequest, employee: User | None = None) -> dict:
    data = {
        "id": r.id,
        "kind": r.kind,
        "topic": r.topic,
        "question": r.question,
        "department": r.department,
        "status": r.status,
        "reply": r.reply,
        "replied_at": r.replied_at,
        "added_to_knowledge": r.added_to_knowledge,
        "seen": r.seen_by_employee,
        "created_at": r.created_at,
    }
    if employee is not None:
        data["employee"] = {"id": employee.id, "email": employee.email, "job_title": employee.job_title}
    return data


def create_unanswered(db: Session, user_id: int, question: str, message_id: int) -> None:
    """Called by the chat route when Humanly replies "This isn't covered"."""
    user = db.get(User, user_id)
    db.add(HRRequest(user_id=user_id, department=user.department if user else None, kind="unanswered",
                     topic="Not covered by a policy", question=question, message_id=message_id))


def _teach(db: Session, req: HRRequest, admin: User) -> None:
    """Adds the HR reply to ChromaDB under an "HR Answers" document, so retrieval finds it."""
    from app.retrieval.vector_store import add_chunks  # loads the embedding model only when needed

    doc = (db.query(Document)
           .filter(Document.title == HR_ANSWERS_TITLE, Document.is_active.is_(True)).first())
    if doc is None:
        doc = Document(title=HR_ANSWERS_TITLE, filename="hr_answers", version="2026",
                       uploaded_by=admin.id, is_active=True, chunk_count=0)
        db.add(doc)
        db.flush()
        doc.family_id = doc.id

    section = f"HR answer: {req.question[:80]}"
    text = f"{section}\nQuestion: {req.question}\nAnswer from HR: {req.reply}"
    meta = {"document_id": doc.id, "family_id": doc.family_id, "is_active": True,
            "title": HR_ANSWERS_TITLE, "version": doc.version, "section": section, "chunk_index": req.id}
    add_chunks([f"doc{doc.id}_faq{req.id}"], [text], [meta])
    doc.chunk_count = (doc.chunk_count or 0) + 1
    req.added_to_knowledge = True


# ---------- Employee ----------

@router.get("/topics")
def topics():
    return TOPICS


@router.post("")
def ask_hr(body: NewRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please write your question")
    req = HRRequest(user_id=user.id, department=user.department, kind="private",
                    topic=body.topic if body.topic in TOPICS else "Other", question=question)
    db.add(req)
    db.commit()
    db.refresh(req)
    return _out(req)


@router.get("/mine")
def my_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reqs = (db.query(HRRequest).filter(HRRequest.user_id == user.id)
            .order_by(HRRequest.created_at.desc()).all())
    return {"items": [_out(r) for r in reqs],
            "unseen": sum(1 for r in reqs if not r.seen_by_employee)}


@router.post("/mine/seen")
def mark_seen(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(HRRequest).filter(HRRequest.user_id == user.id,
                               HRRequest.seen_by_employee.is_(False)).update({"seen_by_employee": True})
    db.commit()
    return {"ok": True}


# ---------- HR ----------

@router.get("")
def inbox(status: str | None = None, department: str | None = None,
          db: Session = Depends(get_db), _: User = Depends(require_hr_admin)):
    q = db.query(HRRequest, User).join(User, HRRequest.user_id == User.id)
    if status:
        q = q.filter(HRRequest.status == status)
    if department:
        q = q.filter(HRRequest.department == department)
    rows = q.order_by(HRRequest.status.desc(), HRRequest.created_at.desc()).all()  # open first
    return [_out(r, u) for r, u in rows]


@router.post("/{request_id}/reply")
def reply(request_id: int, body: Reply, db: Session = Depends(get_db),
          admin: User = Depends(require_hr_admin)):
    req = db.get(HRRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Request not found")
    text = body.reply.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please write a reply")
    if body.teach and req.kind == "private":
        raise HTTPException(status_code=400, detail="Private questions are never added to Humanly's knowledge")

    req.reply = text
    req.status = "answered"
    req.replied_by = admin.id
    req.replied_at = datetime.now(timezone.utc)
    req.seen_by_employee = False
    if body.teach and not req.added_to_knowledge:
        try:
            _teach(db, req, admin)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Saved nothing: could not add to knowledge ({e})")
    db.commit()
    db.refresh(req)
    return _out(req, db.get(User, req.user_id))
