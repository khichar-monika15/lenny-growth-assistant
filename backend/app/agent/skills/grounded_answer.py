"""Default skill: answer product and growth questions from the transcripts."""
from typing import ClassVar, Optional

from .base import Skill, SkillContext, SkillPlan

SYSTEM_PROMPT = """You are Lenny's Growth Assistant. You answer product management \
and growth questions using only the transcript excerpts provided below.

Rules:
- Ground every claim in the excerpts. Cite the guest or episode by name when you \
use their point, for example "Jen Abel argues that...".
- If the excerpts do not cover the question, say so plainly and name what is \
missing. Never fill the gap from general knowledge.
- Prefer the specifics in the excerpts (numbers, examples, step names) over \
generic advice.
- Be direct and concrete. Skip preamble.

Transcript excerpts:
{context}"""

NO_CONTEXT_PROMPT = """You are Lenny's Growth Assistant. The transcript index \
returned nothing relevant for this question.

Tell the user you cannot answer from Lenny's Podcast transcripts, in one or two \
sentences. Suggest how they might rephrase, or name what the index would need to \
cover. Do not answer from general knowledge and do not invent citations."""


class GroundedAnswerSkill(Skill):
    """Conversational Q&A grounded in retrieved transcript chunks."""

    name: ClassVar[str] = "grounded_answer"
    description: ClassVar[str] = (
        "Answer a product or growth question using Lenny's Podcast transcripts"
    )
    retrieval_top_k: ClassVar[Optional[int]] = None

    #: A follow-up like "what about that?" carries no searchable meaning alone,
    #: so the previous user turn is folded into the retrieval query. This is
    #: cheaper and more predictable than an extra LLM call to rewrite it.
    STANDALONE_QUERY_WORDS: ClassVar[int] = 6

    def retrieval_query(self, context: SkillContext) -> str:
        message = context.message
        if not context.history or len(message.split()) > self.STANDALONE_QUERY_WORDS:
            return message

        previous = next(
            (turn["content"] for turn in reversed(context.history) if turn["role"] == "user"),
            None,
        )
        return f"{previous}\n{message}" if previous else message

    def plan(self, context: SkillContext) -> SkillPlan:
        assembled = context.assembled

        if assembled is None or assembled.is_empty:
            system_prompt = NO_CONTEXT_PROMPT
        else:
            system_prompt = SYSTEM_PROMPT.format(context=assembled.context)

        return SkillPlan(
            system_prompt=system_prompt,
            messages=[*context.history, {"role": "user", "content": context.message}],
            max_tokens=2048,
            temperature=0.4,
        )
