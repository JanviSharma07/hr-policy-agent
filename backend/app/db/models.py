from datetime import date, datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, Date, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="employee")  # employee | hr_admin
    # Employee profile, used by the eligibility and calculator agents
    join_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)   # e.g. L3; set by HR, not shown to employees
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)        # e.g. ["Python", "SQL"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    """Document registry. Each upload or replacement is one row (one version).
    All versions of the same policy share a family_id; only one is active."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(30), nullable=True)    # which agent answered
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)     # 1 helpful, -1 not helpful
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HRRequest(Base):
    """A question for a human in HR. Either the employee sent it privately (never shown to the AI),
    or Humanly couldn't answer it and passed it on automatically."""
    __tablename__ = "hr_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)  # routes it to that department's HR
    kind: Mapped[str] = mapped_column(String(20))            # private | unanswered
    topic: Mapped[str | None] = mapped_column(String(60), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the AI answer it came from
    status: Mapped[str] = mapped_column(String(20), default="open")         # open | answered
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    added_to_knowledge: Mapped[bool] = mapped_column(Boolean, default=False)  # reply taught to Humanly
    seen_by_employee: Mapped[bool] = mapped_column(Boolean, default=True)    # False until they read the reply
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True, index=True)  # not called "date": that shadows the type
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20), default="fixed")  # fixed | optional
