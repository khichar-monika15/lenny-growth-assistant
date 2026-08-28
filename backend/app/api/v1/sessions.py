"""Session management endpoints."""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import to_http_exception
from app.api.v1.schemas import (
    ErrorResponse,
    MessageOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
)
from app.database import get_db
from app.llm.factory import resolve_provider
from app.services import session_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new chat session",
)
async def create_session(
    payload: SessionCreate, db: AsyncSession = Depends(get_db)
) -> SessionOut:
    """Create an empty session. Each session keeps its own conversation context."""
    try:
        resolved = resolve_provider(payload.model_provider)
        session = await session_service.create_session(
            db,
            model_provider=resolved.name,
            model_name=resolved.model,
            title=payload.title,
        )
    except Exception as exc:  # noqa: BLE001
        raise to_http_exception(exc) from exc

    return SessionOut.model_validate(session)


@router.get("", response_model=List[SessionOut], summary="List sessions, newest first")
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[SessionOut]:
    sessions = await session_service.list_sessions(db, limit=limit)
    return [SessionOut.model_validate(s) for s in sessions]


@router.get(
    "/{session_id}",
    response_model=SessionDetail,
    responses={404: {"model": ErrorResponse}},
    summary="Get a session with its full message history",
)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> SessionDetail:
    try:
        session = await session_service.get_session(db, session_id)
        messages = await session_service.list_messages(db, session_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_exception(exc) from exc

    return SessionDetail(
        **SessionOut.model_validate(session).model_dump(),
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.get(
    "/{session_id}/messages",
    response_model=List[MessageOut],
    responses={404: {"model": ErrorResponse}},
    summary="Get a session's messages",
)
async def get_messages(
    session_id: UUID, db: AsyncSession = Depends(get_db)
) -> List[MessageOut]:
    try:
        await session_service.get_session(db, session_id)
        messages = await session_service.list_messages(db, session_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_exception(exc) from exc

    return [MessageOut.model_validate(m) for m in messages]


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a session and its messages",
)
async def delete_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        await session_service.delete_session(db, session_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_exception(exc) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
