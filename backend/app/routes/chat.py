from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Conversation, Message, User
from app.auth.dependencies import get_current_user
from app.agent.graph import run_agent

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None  # leave empty to start a new chat


def _own_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:  # users can only see their own chats
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("")
def chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    if body.conversation_id:
        conv = _own_conversation(db, body.conversation_id, user)
    else:
        conv = Conversation(user_id=user.id, title=question[:60])
        db.add(conv)
        db.flush()

    try:
        result = run_agent(question)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Agent failed: {e}")

    db.add(Message(conversation_id=conv.id, sender="user", content=question))
    db.add(Message(conversation_id=conv.id, sender="assistant",
                   content=result["answer"], citations=result["citations"]))
    db.commit()
    return {"conversation_id": conv.id, **result}


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convs = (db.query(Conversation).filter(Conversation.user_id == user.id)
             .order_by(Conversation.created_at.desc()).all())
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in convs]


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    conv = _own_conversation(db, conversation_id, user)
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
    conv = _own_conversation(db, conversation_id, user)
    db.delete(conv)  # messages are removed too (ON DELETE CASCADE)
    db.commit()
    return {"deleted": conversation_id}