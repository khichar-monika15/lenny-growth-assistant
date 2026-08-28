"""Ship 30 for 30 essay generation endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.config import get_settings
from app.llm.factory import LLMProviderFactory
from app.rag.retriever import VectorRetriever
from app.rag.context_assembler import ContextAssembler
from app.services.embedding_service import EmbeddingService

router = APIRouter()
settings = get_settings()


class Ship30Request(BaseModel):
    """Ship 30 essay generation request."""
    topic: str = Field(..., description="Essay topic")
    word_count: int = Field(default=300, ge=250, le=1250, description="Target word count")
    hook_style: str = Field(default="question", description="Hook style: question, stat, story, contrarian")
    model_provider: Optional[str] = None


@router.post("/ship30/generate")
async def generate_ship30_essay(request: Ship30Request):
    """
    Generate a Ship 30 for 30 style essay.

    Structure: Hook → Body → CTA
    Style: Terse, scannable, actionable
    Grounding: All claims backed by Lenny's transcripts
    """
    try:
        # Initialize components
        retriever = VectorRetriever(
            chroma_host=settings.CHROMA_HOST,
            chroma_port=settings.CHROMA_PORT,
            collection_name=settings.CHROMA_COLLECTION_NAME
        )
        await retriever.initialize()

        context_assembler = ContextAssembler(max_tokens=settings.CONTEXT_MAX_TOKENS)

        # Generate embedding
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.generate_embedding(request.topic)
        await embedding_service.close()

        # Retrieve relevant content
        chunks = await retriever.retrieve(query_embedding, top_k=15)
        assembled = context_assembler.assemble_context(chunks)

        # Get LLM provider
        provider_name = request.model_provider or settings.DEFAULT_MODEL
        if provider_name == "claude":
            if not settings.ANTHROPIC_API_KEY:
                provider_name = "ollama"  # Fallback

            config = {
                "api_key": settings.ANTHROPIC_API_KEY,
                "model": "claude-3-5-sonnet-20241022"
            }
        else:
            config = {
                "base_url": settings.OLLAMA_BASE_URL,
                "model": settings.OLLAMA_CHAT_MODEL
            }

        llm = LLMProviderFactory.create_provider(provider_name, config)

        # Build prompt
        system_prompt = f"""You are an expert at writing Ship 30 for 30 atomic essays.

STRICT REQUIREMENTS:
- Word count: EXACTLY {request.word_count} words (±10 words acceptable)
- Structure: Hook → Body → CTA
- Hook style: {request.hook_style}
- Style: Terse, scannable, one-sentence paragraphs
- Grounding: All claims must come from the provided context

CONTEXT from Lenny's Podcast:
{assembled.context}

Write ONLY the essay. No preamble, no meta-commentary."""

        messages = [
            {"role": "user", "content": f"Write a Ship 30 essay about: {request.topic}"}
        ]

        # Generate essay
        response = await llm.generate(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7
        )

        essay_content = response["content"]
        word_count = len(essay_content.split())

        # Validate word count (allow ±10% tolerance)
        min_words = int(request.word_count * 0.9)
        max_words = int(request.word_count * 1.1)

        if not (min_words <= word_count <= max_words):
            # Retry once with explicit word count feedback
            retry_prompt = f"""The previous essay was {word_count} words, but needs to be {request.word_count} words.

Rewrite it to EXACTLY {request.word_count} words (±10 acceptable). Keep the same topic and structure."""

            messages.append({"role": "assistant", "content": essay_content})
            messages.append({"role": "user", "content": retry_prompt})

            retry_response = await llm.generate(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=1500
            )

            essay_content = retry_response["content"]
            word_count = len(essay_content.split())

        return {
            "essay": essay_content,
            "word_count": word_count,
            "target_word_count": request.word_count,
            "sources": assembled.sources,
            "model_provider": provider_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Essay generation failed: {str(e)}")
