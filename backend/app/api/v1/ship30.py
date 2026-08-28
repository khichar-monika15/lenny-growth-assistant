"""Ship 30 for 30 essay generation endpoint."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.ship30 import DEFAULT_HOOK_STYLE, HOOK_STYLES, Ship30Skill
from app.api.errors import to_http_exception
from app.api.v1.schemas import ErrorResponse, Ship30Request, Ship30Response
from app.database import get_db
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ship30/hook-styles", summary="Available Ship 30 hook styles")
async def hook_styles() -> dict:
    """The hook taxonomy the skill encodes, for populating the UI."""
    return {"default": DEFAULT_HOOK_STYLE, "styles": HOOK_STYLES}


@router.post(
    "/ship30/generate",
    response_model=Ship30Response,
    responses={503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    summary="Generate a Ship 30 for 30 style essay",
)
async def generate_ship30_essay(
    request: Ship30Request, db: AsyncSession = Depends(get_db)
) -> Ship30Response:
    """
    Write an essay grounded in the transcripts, using the Ship 30 skill.

    The essay is persisted to the session as a normal assistant turn and
    returned as a Markdown artifact for the viewer.
    """
    if request.hook_style not in HOOK_STYLES:
        raise to_http_exception(
            ValueError(
                f"Unknown hook_style '{request.hook_style}'. "
                f"Expected one of: {', '.join(HOOK_STYLES)}"
            )
        )

    try:
        turn = await chat_service.send_message(
            db,
            message=f"Write a Ship 30 essay about: {request.topic}",
            session_id=request.session_id,
            model_provider=request.model_provider,
            forced_skill=Ship30Skill.name,
            options={
                "topic": request.topic,
                "word_count": request.word_count,
                "hook_style": request.hook_style,
            },
        )
    except Exception as exc:  # noqa: BLE001 - translated to a safe response
        raise to_http_exception(exc) from exc

    return Ship30Response(
        session_id=turn.session_id,
        essay=turn.message,
        artifact=turn.artifact,
        word_count=turn.metadata.get("word_count", 0),
        target_word_count=turn.metadata.get("target_word_count", request.word_count),
        within_tolerance=turn.metadata.get("within_tolerance", False),
        hook_style=turn.metadata.get("hook_style", request.hook_style),
        sources=turn.sources,
        provider=turn.provider,
        model=turn.model,
        fallback_reason=turn.fallback_reason,
    )
