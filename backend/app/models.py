"""Database models using SQLAlchemy."""
from sqlalchemy import Column, String, Integer, Text, Boolean, TIMESTAMP, ForeignKey, ARRAY, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()


class Session(Base):
    """Chat session."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), default="anonymous")
    title = Column(String(255))
    model_provider = Column(String(50), default="ollama")
    model_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    extra_metadata = Column("metadata", JSONB, default={})


class Message(Base):
    """Conversation message."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    sources = Column(JSONB, default=[])
    token_count = Column(Integer)
    model_provider = Column(String(50))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    extra_metadata = Column("metadata", JSONB, default={})


class Transcript(Base):
    """Podcast transcript."""
    __tablename__ = "transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_path = Column(String(500), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    publication_date = Column(Date)
    guests = Column(ARRAY(Text))
    word_count = Column(Integer)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    extra_metadata = Column("metadata", JSONB, default={})


class Chunk(Base):
    """Transcript chunk."""
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"))
    chroma_id = Column(String(255), unique=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False)
    start_char = Column(Integer)
    end_char = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    extra_metadata = Column("metadata", JSONB, default={})
