"""HR-only pages: the employee directory and the insights dashboard."""
from collections import Counter
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Conversation, HRRequest, Message, User
from app.auth.dependencies import require_hr_admin
from app.routes.auth import clean_skills, user_out

router = APIRouter(prefix="/hr", tags=["hr"])

INTENT_LABELS = {
    "policy_qa": "Policy questions",
    "calculation": "Calculations",
    "eligibility": "Eligibility checks",
    "compare": "Version comparisons",
    "summarize": "Summaries",
    "out_of_scope": "Out of scope",
}


class EmployeeUpdate(BaseModel):
    department: str | None = None
    job_title: str | None = None
    grade: str | None = None
    city: str | None = None
    join_date: date | None = None
    skills: list[str] | None = None


def _is_unanswered(answer: str) -> bool:
    return answer.lower().startswith("this isn't covered")


# ---------- Employee directory ----------

@router.get("/employees")
def list_employees(db: Session = Depends(get_db), _: User = Depends(require_hr_admin)):
    asked = Counter(
        user_id for (user_id,) in
        db.query(Conversation.user_id).join(Message, Message.conversation_id == Conversation.id)
        .filter(Message.sender == "user").all()
    )
    users = db.query(User).order_by(User.role.desc(), User.email).all()
    return [{**user_out(u, include_grade=True), "questions_asked": asked.get(u.id, 0)} for u in users]


@router.patch("/employees/{user_id}")
def update_employee(user_id: int, body: EmployeeUpdate, db: Session = Depends(get_db),
                    _: User = Depends(require_hr_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "skills":
            value = clean_skills(value)
        elif isinstance(value, str):
            value = value.strip() or None
            if field == "grade" and value:
                value = value.upper()
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user_out(user, include_grade=True)


# ---------- Insights ----------

@router.get("/insights")
def insights(db: Session = Depends(get_db), _: User = Depends(require_hr_admin)):
    rows = (db.query(Message, User.department)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .join(User, Conversation.user_id == User.id)
            .order_by(Message.conversation_id, Message.id).all())

    # Pair each answer with the question that came just before it in the same chat
    pairs, last_question = [], {}
    for msg, department in rows:
        if msg.sender == "user":
            last_question[msg.conversation_id] = msg
        elif msg.sender == "assistant":
            q = last_question.get(msg.conversation_id)
            pairs.append({
                "message_id": msg.id,
                "question": q.content if q else "",
                "answer": msg.content,
                "intent": msg.intent,
                "feedback": msg.feedback,
                "department": department or "Not set",
                "asked_at": msg.created_at,
            })

    helpful = sum(1 for p in pairs if p["feedback"] == 1)
    not_helpful = sum(1 for p in pairs if p["feedback"] == -1)
    unanswered = [p for p in pairs if _is_unanswered(p["answer"])]
    newest = lambda items: sorted(items, key=lambda p: p["asked_at"], reverse=True)[:10]

    by_intent = Counter(INTENT_LABELS.get(p["intent"], "Other") for p in pairs if p["intent"])
    by_department = Counter(p["department"] for p in pairs)
    employees = {u_id for (u_id,) in db.query(Conversation.user_id).distinct().all()}
    replied = {m_id for (m_id,) in db.query(HRRequest.message_id)
               .filter(HRRequest.message_id.isnot(None), HRRequest.status == "answered").all()}

    return {
        "totals": {
            "questions": len(pairs),
            "employees_asking": len(employees),
            "helpful": helpful,
            "not_helpful": not_helpful,
            "helpful_rate": round(100 * helpful / (helpful + not_helpful)) if helpful + not_helpful else None,
            "unanswered": len(unanswered),
        },
        "by_intent": [{"label": k, "count": v} for k, v in by_intent.most_common()],
        "by_department": [{"label": k, "count": v} for k, v in by_department.most_common()],
        "unanswered": [{"question": p["question"], "department": p["department"], "asked_at": p["asked_at"],
                        "hr_replied": p["message_id"] in replied}
                       for p in newest(unanswered)],
        "not_helpful": [{"question": p["question"], "answer": p["answer"][:300], "intent": p["intent"],
                         "asked_at": p["asked_at"]}
                        for p in newest([p for p in pairs if p["feedback"] == -1])],
    }
