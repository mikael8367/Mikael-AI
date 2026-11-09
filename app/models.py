from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    return datetime.now(timezone.utc)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="Nova conversa")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")

class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default="contexto")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    extracted_text: Mapped[str] = mapped_column(Text)
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PendingAction(Base):
    __tablename__ = "pending_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    arguments: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    expires_at: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Connector(Base):
    __tablename__ = "connectors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(120))
    endpoint: Mapped[str] = mapped_column(Text, default="")
    account: Mapped[str] = mapped_column(String(180), default="")
    secret: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    tool_permissions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
