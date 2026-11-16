import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.db.models import Conversation, Message, User
from app.auth.dependencies import get_current_user
from app.agent.graph import run_agent, stream_agent, HISTORY_MESSAGES
from app.routes.hr_requests import create_unanswered

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None  # leave empty to start a new chat


class FeedbackRequest(BaseModel):
    value: int  # 1 = helpful, -1 = not helpful, 0 = remove the rating


# ---------- Helpers ----------

def _own_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:  # users can only see their own chats
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _clean_question(body: ChatRequest) -> str:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    return question


def _profile(user: User) -> dict:
    return {"join_date": user.join_date, "grade": user.grade, "city": user.city,
            "department": user.department, "job_title": user.job_title}


def _history(db: Session, conversation_id: int | None) -> list[dict]:
    if not conversation_id:
        return []
    msgs = (db.query(Message).filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc()).limit(HISTORY_MESSAGES).all())
    return [{"sender": m.sender, "content": m.content} for m in reversed(msgs)]


def _save(db: Session, conversation_id: int | None, user_id: int, question: str,
          result: dict) -> tuple[int, int]:
    """Saves the question and answer. Returns (conversation id, answer message id)."""
    if conversation_id:
        conv = _own_conversation(db, conversation_id, user_id)
    else:
        conv = Conversation(user_id=user_id, title=question[:60])
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, sender="user", content=question))
    answer = Message(conversation_id=conv.id, sender="assistant", content=result["answer"],
                     citations=result["citations"], intent=result.get("intent"))
    db.add(answer)
    db.flush()
    if result["answer"].lower().startswith("this isn't covered"):
        create_unanswered(db, user_id, question, answer.id)  # HR sees it in the HR Inbox
    db.commit()
    return conv.id, answer.id


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


# ---------- Routes ----------

@router.post("")
def chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question = _clean_question(body)
    if body.conversation_id:
        _own_conversation(db, body.conversation_id, user.id)

    try:
        result = run_agent(question, _profile(user), _history(db, body.conversation_id))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent failed: {e}")

    conversation_id, message_id = _save(db, body.conversation_id, user.id, question, result)
    return {"conversation_id": conversation_id, "message_id": message_id, **result}


@router.post("/stream")
def chat_stream(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Same as POST /chat, but sends each agent step live (Server-Sent Events).
    Events: "step" {text}, then "done" {conversation_id, intent, answer, citations, trace},
    or "error" {detail}."""
    question = _clean_question(body)
    if body.conversation_id:
        _own_conversation(db, body.conversation_id, user.id)
    profile, history, user_id = _profile(user), _history(db, body.conversation_id), user.id

    def events():
        session = SessionLocal()  # own session: the request's one closes before streaming ends
        try:
            for kind, payload in stream_agent(question, profile, history):
                if kind == "step":
                    yield _sse("step", {"text": payload})
                else:
                    conversation_id, message_id = _save(session, body.conversation_id, user_id, question, payload)
                    yield _sse("done", {"conversation_id": conversation_id, "message_id": message_id, **payload})
        except Exception as e:
            session.rollback()
            yield _sse("error", {"detail": f"Agent failed: {e}"})
        finally:
            session.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convs = (db.query(Conversation).filter(Conversation.user_id == user.id)
             .order_by(Conversation.created_at.desc()).all())
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in convs]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    conv = _own_conversation(db, conversation_id, user.id)
    msgs = (db.query(Message).filter(Message.conversation_id == conv.id)
            .order_by(Message.id).all())
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {"id": m.id, "sender": m.sender, "content": m.content, "citations": m.citations,
             "feedback": m.feedback, "created_at": m.created_at}
            for m in msgs
        ],
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    conv = _own_conversation(db, conversation_id, user.id)
    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    db.delete(conv)
    db.commit()
    return {"deleted": conversation_id}


@router.post("/messages/{message_id}/feedback")
def give_feedback(message_id: int, body: FeedbackRequest, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """Thumbs up / down on an answer. HR sees the results on the Insights page."""
    msg = db.get(Message, message_id)
    if msg is None or msg.sender != "assistant":
        raise HTTPException(status_code=404, detail="Answer not found")
    _own_conversation(db, msg.conversation_id, user.id)
    if body.value not in (1, -1, 0):
        raise HTTPException(status_code=400, detail="value must be 1, -1 or 0")
    msg.feedback = body.value or None
    db.commit()
    return {"message_id": msg.id, "feedback": msg.feedback}
