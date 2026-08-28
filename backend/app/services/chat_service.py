"""
Chat orchestration.

One path handles both streaming and non-streaming turns: resolve the session,
route to a skill, retrieve, generate, then persist. Streaming and blocking
requests therefore produce identical stored history and citations.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.router import AgentRouter
from app.agent.skills.base import SkillContext, SkillResult
from app.config import get_settings
from app.llm.factory import ResolvedProvider, resolve_provider
from app.rag.chroma import VectorStoreUnavailable
from app.rag.context_assembler import AssembledContext, ContextAssembler
from app.rag.retriever import VectorRetriever
from app.services import session_service
from app.services.embedding_service import EmbeddingError, EmbeddingService

logger = logging.getLogger(__name__)

router = AgentRouter()


@dataclass
class ChatTurn:
    """The outcome of one completed turn."""
    session_id: UUID
    message: str
    sources: List[dict] = field(default_factory=list)
    artifact: Optional[dict] = None
    intent: str = "grounded_answer"
    provider: str = "ollama"
    model: str = ""
    fallback_reason: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "message": self.message,
            "sources": self.sources,
            "artifact": self.artifact,
            "intent": self.intent,
            "provider": self.provider,
            "model": self.model,
            "fallback_reason": self.fallback_reason,
            "usage": self.usage,
            "metadata": self.metadata,
        }


@dataclass
class _Prepared:
    """Everything resolved before the model is called."""
    session: Any
    route: Any
    context: SkillContext
    plan: Any
    assembled: AssembledContext
    resolved: ResolvedProvider
    retrieval_error: Optional[str] = None


async def _retrieve(query: str, top_k: int) -> tuple[AssembledContext, Optional[str]]:
    """
    Retrieve and assemble context.

    Returns empty context plus a reason when retrieval could not run, so the
    caller can tell the user their answer is ungrounded instead of quietly
    pretending the index had nothing to say.
    """
    settings = get_settings()
    embedding_service = EmbeddingService()

    try:
        query_embedding = await embedding_service.generate_embedding(query)
        retriever = VectorRetriever()
        await retriever.initialize()
        chunks = await retriever.retrieve(query_embedding, top_k=top_k)
    except (VectorStoreUnavailable, EmbeddingError) as exc:
        logger.error("Retrieval failed: %s", exc)
        return AssembledContext(context=""), str(exc)
    finally:
        await embedding_service.close()

    assembled = ContextAssembler(max_tokens=settings.CONTEXT_MAX_TOKENS).assemble_context(chunks)
    if assembled.is_empty:
        logger.info("No chunks passed the similarity floor for query: %r", query[:80])

    return assembled, None


async def _prepare(
    db: AsyncSession,
    message: str,
    session_id: Optional[UUID],
    model_provider: Optional[str],
    forced_skill: Optional[str],
    options: Optional[Dict[str, Any]],
) -> _Prepared:
    settings = get_settings()
    resolved = resolve_provider(model_provider)

    session = await session_service.get_or_create(db, session_id, resolved.name)
    history = await session_service.load_history(db, session.id)

    await session_service.add_message(db, session.id, "user", message)
    await session_service.touch(db, session, first_message=message)

    route = router.route(message, forced_skill=forced_skill, has_history=bool(history))
    route.options.update(options or {})

    context = SkillContext(message=message, history=history, options=route.options)
    top_k = route.skill.retrieval_top_k or settings.RETRIEVAL_TOP_K
    assembled, retrieval_error = await _retrieve(route.skill.retrieval_query(context), top_k)
    context.assembled = assembled

    logger.info(
        "Routed to %s (%s); %d sources; provider=%s",
        route.intent,
        route.reason,
        assembled.total_chunks,
        resolved.name,
    )

    return _Prepared(
        session=session,
        route=route,
        context=context,
        plan=route.skill.plan(context),
        assembled=assembled,
        resolved=resolved,
        retrieval_error=retrieval_error,
    )


async def _persist(
    db: AsyncSession, prepared: _Prepared, result: SkillResult, usage: Dict[str, int]
) -> ChatTurn:
    metadata = {
        "intent": prepared.route.intent,
        "routing_reason": prepared.route.reason,
        **result.metadata,
    }
    if prepared.retrieval_error:
        metadata["retrieval_error"] = prepared.retrieval_error
    if result.artifact:
        metadata["artifact"] = result.artifact.to_dict()

    await session_service.add_message(
        db,
        prepared.session.id,
        "assistant",
        result.content,
        sources=prepared.assembled.sources,
        token_count=usage.get("output_tokens"),
        model_provider=prepared.resolved.name,
        metadata=metadata,
    )

    return ChatTurn(
        session_id=prepared.session.id,
        message=result.content,
        sources=prepared.assembled.sources,
        artifact=result.artifact.to_dict() if result.artifact else None,
        intent=prepared.route.intent,
        provider=prepared.resolved.name,
        model=prepared.resolved.model,
        fallback_reason=prepared.resolved.fallback_reason,
        usage=usage,
        metadata=metadata,
    )


async def send_message(
    db: AsyncSession,
    message: str,
    session_id: Optional[UUID] = None,
    model_provider: Optional[str] = None,
    forced_skill: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> ChatTurn:
    """Run a full turn and return the completed result."""
    prepared = await _prepare(db, message, session_id, model_provider, forced_skill, options)

    try:
        response = await prepared.resolved.provider.generate(
            messages=prepared.plan.messages,
            system_prompt=prepared.plan.system_prompt,
            max_tokens=prepared.plan.max_tokens,
            temperature=prepared.plan.temperature,
        )
    finally:
        await prepared.resolved.provider.aclose()

    result = prepared.route.skill.finalize(response["content"], prepared.context)
    return await _persist(db, prepared, result, response.get("usage", {}))


async def stream_message(
    db: AsyncSession,
    message: str,
    session_id: Optional[UUID] = None,
    model_provider: Optional[str] = None,
    forced_skill: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run a turn, yielding SSE-shaped events.

    Event order: session -> retrieval_start -> sources -> content_delta* ->
    artifact? -> message_stop. An error event is always followed by
    message_stop so the client can never be left waiting.
    """
    prepared = await _prepare(db, message, session_id, model_provider, forced_skill, options)

    yield {
        "type": "session",
        "session_id": str(prepared.session.id),
        "intent": prepared.route.intent,
        "provider": prepared.resolved.name,
        "model": prepared.resolved.model,
        "fallback_reason": prepared.resolved.fallback_reason,
    }
    yield {
        "type": "sources",
        "sources": prepared.assembled.sources,
        "retrieval_error": prepared.retrieval_error,
    }

    collected: List[str] = []
    usage: Dict[str, int] = {}

    try:
        async for event in prepared.resolved.provider.stream(
            messages=prepared.plan.messages,
            system_prompt=prepared.plan.system_prompt,
            max_tokens=prepared.plan.max_tokens,
            temperature=prepared.plan.temperature,
        ):
            if event["type"] == "content_delta":
                collected.append(event["delta"])
                yield event
            elif event["type"] == "message_stop":
                usage = event.get("usage", {})
    finally:
        await prepared.resolved.provider.aclose()

    result = prepared.route.skill.finalize("".join(collected), prepared.context)
    turn = await _persist(db, prepared, result, usage)

    if turn.artifact:
        yield {"type": "artifact", "artifact": turn.artifact}

    yield {
        "type": "message_stop",
        "usage": usage,
        "metadata": turn.metadata,
        "session_id": str(turn.session_id),
    }
