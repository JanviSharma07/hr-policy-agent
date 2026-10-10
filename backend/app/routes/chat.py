import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db, SessionLocal
from app.db.models import Conversation, Message, User
from app.auth.dependencies import get_current_user
from app.agent.graph import run_agent, stream_agent, HISTORY_MESSAGES

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None  # leave empty to start a new chat


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
    return {"join_date": user.join_date, "grade": user.grade, "city": user.city}


def _history(db: Session, conversation_id: int | None) -> list[dict]:
    if not conversation_id:
        return []
    msgs = (db.query(Message).filter(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc()).limit(HISTORY_MESSAGES).all())
    return [{"sender": m.sender, "content": m.content} for m in reversed(msgs)]


def _save(db: Session, conversation_id: int | None, user_id: int, question: str, result: dict) -> int:
    if conversation_id:
        conv = _own_conversation(db, conversation_id, user_id)
    else:
        conv = Conversation(user_id=user_id, title=question[:60])
        db.add(conv)
        db.flush()
    db.add(Message(conversation_id=conv.id, sender="user", content=question))
    db.add(Message(conversation_id=conv.id, sender="assistant",
                   content=result["answer"], citations=result["citations"]))
    db.commit()
    return conv.id


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

    conversation_id = _save(db, body.conversation_id, user.id, question, result)
    return {"conversation_id": conversation_id, **result}


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
                    conversation_id = _save(session, body.conversation_id, user_id, question, payload)
                    yield _sse("done", {"conversation_id": conversation_id, **payload})
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
            {"sender": m.sender, "content": m.content, "citations": m.citations, "created_at": m.created_at}
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
