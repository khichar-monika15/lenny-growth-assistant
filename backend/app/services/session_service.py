"""Session and message persistence."""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Session

logger = logging.getLogger(__name__)

#: Turns of prior conversation replayed to the model. Enough for follow-ups
#: without pushing retrieved context out of a local model's window.
HISTORY_TURN_LIMIT = 12

TITLE_MAX_LENGTH = 60


class SessionNotFound(LookupError):
    """Raised when a session id does not exist."""


def derive_title(message: str) -> str:
    """First message, trimmed, becomes the session title."""
    flattened = " ".join(message.split())
    if len(flattened) <= TITLE_MAX_LENGTH:
        return flattened or "New chat"
    return flattened[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


async def create_session(
    db: AsyncSession,
    user_id: str = "anonymous",
    model_provider: str = "ollama",
    model_name: Optional[str] = None,
    title: Optional[str] = None,
) -> Session:
    """Start a new chat session."""
    session = Session(
        id=uuid4(),
        user_id=user_id,
        title=title or "New chat",
        model_provider=model_provider,
        model_name=model_name,
        is_active=True,
        extra_metadata={},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: UUID) -> Session:
    """Fetch a session or raise SessionNotFound."""
    session = (
        await db.execute(select(Session).where(Session.id == session_id))
    ).scalar_one_or_none()

    if session is None:
        raise SessionNotFound(f"Session {session_id} not found")
    return session


async def list_sessions(db: AsyncSession, user_id: str = "anonymous", limit: int = 50) -> List[Session]:
    """List a user's sessions, newest first."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_session(db: AsyncSession, session_id: UUID) -> None:
    """Delete a session. Messages cascade."""
    await get_session(db, session_id)
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()


async def get_or_create(
    db: AsyncSession, session_id: Optional[UUID], model_provider: str
) -> Session:
    """Resolve a session id, starting a new session when none was given."""
    if session_id is None:
        return await create_session(db, model_provider=model_provider)
    return await get_session(db, session_id)


async def list_messages(db: AsyncSession, session_id: UUID) -> List[Message]:
    """Full message history for a session, oldest first."""
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def count_messages(db: AsyncSession, session_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Message).where(Message.session_id == session_id)
    )
    return int(result.scalar_one())


async def load_history(db: AsyncSession, session_id: UUID) -> List[Dict[str, str]]:
    """
    Prior turns as provider-ready messages.

    Only role and content are replayed; citations and metadata stay in the
    database rather than being fed back into the prompt.
    """
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURN_LIMIT)
    )
    recent = list(result.scalars().all())
    recent.reverse()
    return [{"role": m.role, "content": m.content} for m in recent if m.content]


async def add_message(
    db: AsyncSession,
    session_id: UUID,
    role: str,
    content: str,
    sources: Optional[List[dict]] = None,
    token_count: Optional[int] = None,
    model_provider: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Message:
    """Persist one message."""
    message = Message(
        id=uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        sources=sources or [],
        token_count=token_count,
        model_provider=model_provider,
        extra_metadata=metadata or {},
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def touch(db: AsyncSession, session: Session, first_message: Optional[str] = None) -> None:
    """Bump updated_at and name the session from its first message."""
    if first_message and session.title in (None, "", "New chat"):
        session.title = derive_title(first_message)
    session.updated_at = func.now()
    await db.commit()
