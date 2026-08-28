"""
Chat endpoints with SSE streaming support.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import logging

from app.config import settings
from app.llm.factory import LLMProviderFactory
from app.rag.retriever import VectorRetriever
from app.rag.context_assembler import ContextAssembler

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None
    model_provider: Optional[str] = None


# Components will be initialized lazily per request
# (avoids startup dependency on ChromaDB being ready)


def get_llm_provider(provider_name: Optional[str] = None):
    """Get LLM provider instance."""
    provider_name = provider_name or settings.DEFAULT_MODEL

    if provider_name == "claude":
        if not settings.ANTHROPIC_API_KEY:
            raise HTTPException(
                status_code=503,
                detail="Anthropic API key not configured. Using Ollama as fallback."
            )
        config = {
            "api_key": settings.ANTHROPIC_API_KEY,
            "model": "claude-3-5-sonnet-20241022"
        }
    else:  # ollama
        config = {
            "base_url": settings.OLLAMA_BASE_URL,
            "model": settings.OLLAMA_CHAT_MODEL
        }

    return LLMProviderFactory.create_provider(provider_name, config)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response via SSE.

    Returns:
        SSE stream with events: retrieval_start, sources, content_delta, message_stop
    """
    async def event_generator():
        try:
            # Step 1: Retrieval
            yield f"data: {json.dumps({'type': 'retrieval_start'})}\n\n"

            # Initialize retriever
            retriever = VectorRetriever(
                chroma_host=settings.CHROMA_HOST,
                chroma_port=settings.CHROMA_PORT,
                collection_name=settings.CHROMA_COLLECTION_NAME
            )
            await retriever.initialize()

            # Generate query embedding (using Ollama for embeddings)
            embedding_provider = LLMProviderFactory.create_provider("ollama", {
                "base_url": settings.OLLAMA_BASE_URL,
                "model": settings.OLLAMA_EMBEDDING_MODEL
            })

            # Generate query embedding
            from app.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            query_embedding = await embedding_service.generate_embedding(request.message)
            await embedding_service.close()

            # Retrieve chunks
            chunks = await retriever.retrieve(
                query_embedding=query_embedding,
                top_k=settings.RETRIEVAL_TOP_K
            )

            # Assemble context
            context_assembler = ContextAssembler(max_tokens=settings.CONTEXT_MAX_TOKENS)
            assembled = context_assembler.assemble_context(chunks)

            # Send sources
            yield f"data: {json.dumps({'type': 'sources', 'sources': assembled.sources})}\n\n"

            # Step 2: Generate response
            llm = get_llm_provider(request.model_provider)

            # Build messages
            system_prompt = f"""You are Lenny's Growth Assistant. Answer questions about product management and growth based on the provided context from Lenny's Podcast.

Context from Lenny's Podcasts:
{assembled.context}

If the context doesn't contain enough information to answer the question, say so clearly and suggest what information you'd need."""

            messages = [
                {"role": "user", "content": request.message}
            ]

            # Stream LLM response
            async for chunk in llm.stream(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.7
            ):
                yield f"data: {json.dumps(chunk)}\n\n"

            # Done
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            error_data = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint.
    """
    # Initialize retriever
    retriever = VectorRetriever(
        chroma_host=settings.CHROMA_HOST,
        chroma_port=settings.CHROMA_PORT,
        collection_name=settings.CHROMA_COLLECTION_NAME
    )
    await retriever.initialize()

    # Generate query embedding
    from app.services.embedding_service import EmbeddingService
    embedding_service = EmbeddingService()
    query_embedding = await embedding_service.generate_embedding(request.message)
    await embedding_service.close()

    # Retrieve and assemble
    chunks = await retriever.retrieve(query_embedding, top_k=settings.RETRIEVAL_TOP_K)
    context_assembler = ContextAssembler(max_tokens=settings.CONTEXT_MAX_TOKENS)
    assembled = context_assembler.assemble_context(chunks)

    # Generate response
    llm = get_llm_provider(request.model_provider)

    system_prompt = f"""You are Lenny's Growth Assistant. Answer questions about product management and growth based on the provided context.

Context:
{assembled.context}"""

    messages = [{"role": "user", "content": request.message}]

    response = await llm.generate(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=2048
    )

    return {
        "message": response["content"],
        "sources": assembled.sources,
        "usage": response["usage"]
    }
