"""Chat endpoints with SSE streaming support."""
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import to_http_exception, to_stream_event
from app.api.v1.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.database import get_db
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Stop nginx and friends buffering the stream into one lump.
    "X-Accel-Buffering": "no",
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    summary="Send a message and wait for the full reply",
)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """
    Route the message to a skill, ground it in the transcripts, and persist the turn.

    Omit `session_id` to start a new session; the id is returned so follow-up
    turns can continue the conversation.
    """
    try:
        turn = await chat_service.send_message(
            db,
            message=request.message,
            session_id=request.session_id,
            model_provider=request.model_provider,
            forced_skill=request.skill,
        )
    except Exception as exc:  # noqa: BLE001 - translated to a safe response
        raise to_http_exception(exc) from exc

    return ChatResponse(**turn.to_dict())


@router.post(
    "/chat/stream",
    summary="Send a message and stream the reply over SSE",
    response_class=StreamingResponse,
)
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Stream a turn as Server-Sent Events.

    Events: `session`, `sources`, `content_delta`*, `artifact`?, `message_stop`.
    On failure an `error` event is emitted and the stream is still terminated
    with `[DONE]`, so a client is never left hanging.
    """

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in chat_service.stream_message(
                db,
                message=request.message,
                session_id=request.session_id,
                model_provider=request.model_provider,
                forced_skill=request.skill,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001 - translated to a safe event
            yield f"data: {json.dumps(to_stream_event(exc))}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=SSE_HEADERS
    )
