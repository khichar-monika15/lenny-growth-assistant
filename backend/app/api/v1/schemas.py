"""Request and response contracts for the v1 API."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.skills.ship30 import (
    DEFAULT_HOOK_STYLE,
    DEFAULT_WORD_COUNT,
    HOOK_STYLES,
    MAX_WORD_COUNT,
    MIN_WORD_COUNT,
)

# "model_" is a protected namespace in pydantic v2; these fields are ours.
_ALLOW_MODEL_PREFIX = ConfigDict(protected_namespaces=())

ProviderName = Optional[str]


class ChatRequest(BaseModel):
    """A user turn."""
    model_config = _ALLOW_MODEL_PREFIX

    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[UUID] = Field(
        default=None, description="Omit to start a new session"
    )
    model_provider: ProviderName = Field(
        default=None, description="'claude' or 'ollama'. Defaults to DEFAULT_MODEL."
    )
    skill: Optional[str] = Field(
        default=None, description="Force a skill instead of routing by intent"
    )


class SourceOut(BaseModel):
    """One cited transcript chunk."""
    index: int
    chunk_id: str
    transcript_title: str
    transcript_date: str = ""
    guests: List[str] = []
    source_url: str = ""
    similarity_score: float


class ArtifactOut(BaseModel):
    """A document rendered in the artifact viewer."""
    type: str
    title: str
    content: str


class ChatResponse(BaseModel):
    """A completed turn."""
    model_config = _ALLOW_MODEL_PREFIX

    session_id: UUID
    message: str
    sources: List[SourceOut] = []
    artifact: Optional[ArtifactOut] = None
    intent: str
    provider: str
    model: str
    fallback_reason: Optional[str] = None
    usage: Dict[str, int] = {}
    metadata: Dict[str, Any] = {}


class SessionCreate(BaseModel):
    """Start a session."""
    model_config = _ALLOW_MODEL_PREFIX

    title: Optional[str] = Field(default=None, max_length=255)
    model_provider: ProviderName = None


class SessionOut(BaseModel):
    """Session summary."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    title: Optional[str]
    user_id: str
    model_provider: Optional[str]
    model_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    """A stored message."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    session_id: UUID
    role: str
    content: str
    sources: List[Dict[str, Any]] = []
    token_count: Optional[int] = None
    model_provider: Optional[str] = None
    created_at: datetime


class SessionDetail(SessionOut):
    """Session with its full history."""
    messages: List[MessageOut] = []


class Ship30Request(BaseModel):
    """Ship 30 essay generation request."""
    model_config = _ALLOW_MODEL_PREFIX

    topic: str = Field(..., min_length=3, max_length=500, description="Essay topic")
    word_count: int = Field(
        default=DEFAULT_WORD_COUNT,
        ge=MIN_WORD_COUNT,
        le=MAX_WORD_COUNT,
        description=f"Target word count ({MIN_WORD_COUNT}-{MAX_WORD_COUNT})",
    )
    hook_style: str = Field(
        default=DEFAULT_HOOK_STYLE,
        description=f"One of: {', '.join(HOOK_STYLES)}",
    )
    session_id: Optional[UUID] = None
    model_provider: ProviderName = None


class Ship30Response(BaseModel):
    """A generated essay."""
    model_config = _ALLOW_MODEL_PREFIX

    session_id: UUID
    essay: str
    artifact: Optional[ArtifactOut] = None
    word_count: int
    target_word_count: int
    within_tolerance: bool
    hook_style: str
    sources: List[SourceOut] = []
    provider: str
    model: str
    fallback_reason: Optional[str] = None


class ErrorResponse(BaseModel):
    """Structured error body returned by every failure path."""
    error: str = Field(..., description="Stable machine-readable code")
    detail: str = Field(..., description="Human-readable explanation")
    hint: Optional[str] = Field(default=None, description="How to fix it")
