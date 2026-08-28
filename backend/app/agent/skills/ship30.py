"""
Ship 30 for 30 essay skill.

The Ship 30 method is encoded here as structured rules - hook taxonomy,
formatting constraints, structural shape and a word-count contract - rather
than as a single hand-written prompt string. Each rule is addressable and
testable on its own, and the prompt is composed from them at call time.

Source: the Ship 30 for 30 atomic essay guide.
"""
import re
from typing import ClassVar, Dict, List, Optional

from .base import Artifact, Skill, SkillContext, SkillPlan, SkillResult

#: The Ship 30 hook taxonomy. The opening line's only job is to earn the second line.
HOOK_STYLES: Dict[str, str] = {
    "question": "Open with a sharp question the reader has already asked themselves.",
    "stat": "Open with a concrete number or result from the transcripts, stated flatly.",
    "story": "Open mid-scene with a specific moment from a guest's experience.",
    "contrarian": "Open by naming the accepted wisdom, then refusing it in the next line.",
}

DEFAULT_HOOK_STYLE = "question"

#: Voice and craft rules that make an essay read as Ship 30 rather than as a blog post.
WRITING_PRINCIPLES: List[str] = [
    "One idea per essay. Every section must serve the single promise in the title.",
    "Write to one reader. Use 'you', never 'we' or 'one'.",
    "Mostly one-sentence paragraphs. Let white space carry the pacing.",
    "Short, declarative sentences. Cut every qualifier that does not change the meaning.",
    "Concrete over abstract: name the number, the company, the step, the person.",
    "No jargon, no throat-clearing, no 'in today's fast-paced world' openings.",
]

#: Layout rules. The essay must survive being skimmed.
FORMATTING_RULES: List[str] = [
    "Start with a single H1 title that promises a specific outcome.",
    "Break the body into H2 sections with descriptive, not generic, headings.",
    "Use bullet or numbered lists wherever the content is a sequence or a set.",
    "Bold only the load-bearing phrase in a section. Three or four per essay, not more.",
    "Close with a section giving one specific action the reader can take today.",
]

#: Word-count band the model must land in.
WORD_COUNT_TOLERANCE = 0.12
MIN_WORD_COUNT = 250
MAX_WORD_COUNT = 1250
DEFAULT_WORD_COUNT = 1250

#: Roughly 1.4 tokens per English word, plus headroom for markdown syntax.
TOKENS_PER_WORD = 2.2
MIN_COMPLETION_TOKENS = 1024


def target_sections(word_count: int) -> int:
    """Ship 30 essays stay skimmable by capping section length near 250 words."""
    return max(1, min(6, round(word_count / 250)))


def completion_tokens(word_count: int) -> int:
    """Token budget that can actually hold the requested essay."""
    return max(MIN_COMPLETION_TOKENS, int(word_count * TOKENS_PER_WORD))


def count_words(text: str) -> int:
    """Word count of the prose, ignoring markdown syntax."""
    without_code = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    without_markup = re.sub(r"[#*_>`\-\[\]()]", " ", without_code)
    return len(without_markup.split())


def within_tolerance(actual: int, target: int) -> bool:
    slack = max(15, int(target * WORD_COUNT_TOLERANCE))
    return abs(actual - target) <= slack


def _numbered(items: List[str]) -> str:
    return "\n".join(f"{i}. {rule}" for i, rule in enumerate(items, start=1))


def build_system_prompt(topic: str, word_count: int, hook_style: str, context: str) -> str:
    """Compose the Ship 30 rules into a provider system prompt."""
    hook_instruction = HOOK_STYLES.get(hook_style, HOOK_STYLES[DEFAULT_HOOK_STYLE])
    sections = target_sections(word_count)

    return f"""You write Ship 30 for 30 atomic essays.

TOPIC
{topic}

LENGTH CONTRACT
Write {word_count} words, plus or minus {max(15, int(word_count * WORD_COUNT_TOLERANCE))}.
Shape it as roughly {sections} body section(s) so no section outruns a skim.

HOOK
{hook_instruction}
The first line's only job is to earn the second line.

WRITING PRINCIPLES
{_numbered(WRITING_PRINCIPLES)}

FORMATTING
{_numbered(FORMATTING_RULES)}

GROUNDING
Every claim, number and example must come from the transcript excerpts below.
Attribute borrowed ideas to the guest by name in the prose.
If the excerpts do not support a point you want to make, leave it out.

TRANSCRIPT EXCERPTS
{context}

Output the essay as Markdown and nothing else. No preamble, no commentary, no
word count, no notes about what you did."""


class Ship30Skill(Skill):
    """Turns grounded material into a Ship 30 for 30 style essay."""

    name: ClassVar[str] = "ship30_essay"
    description: ClassVar[str] = (
        "Write a Ship 30 for 30 style atomic essay grounded in Lenny's Podcast transcripts"
    )
    #: Essays span more ground than a single answer, so they retrieve wider.
    retrieval_top_k: ClassVar[Optional[int]] = 15

    def retrieval_query(self, context: SkillContext) -> str:
        return context.options.get("topic") or context.message

    def plan(self, context: SkillContext) -> SkillPlan:
        topic = context.options.get("topic") or context.message
        word_count = int(context.options.get("word_count") or DEFAULT_WORD_COUNT)
        hook_style = context.options.get("hook_style") or DEFAULT_HOOK_STYLE
        assembled = context.assembled
        excerpts = assembled.context if assembled and not assembled.is_empty else ""

        return SkillPlan(
            system_prompt=build_system_prompt(topic, word_count, hook_style, excerpts),
            messages=[{"role": "user", "content": f"Write the essay about: {topic}"}],
            max_tokens=completion_tokens(word_count),
            temperature=0.7,
        )

    def finalize(self, text: str, context: SkillContext) -> SkillResult:
        essay = text.strip()
        target = int(context.options.get("word_count") or DEFAULT_WORD_COUNT)
        actual = count_words(essay)
        title = self._title(essay, context)

        return SkillResult(
            content=essay,
            artifact=Artifact(type="markdown", title=title, content=essay),
            metadata={
                "word_count": actual,
                "target_word_count": target,
                "within_tolerance": within_tolerance(actual, target),
                "hook_style": context.options.get("hook_style") or DEFAULT_HOOK_STYLE,
            },
        )

    @staticmethod
    def _title(essay: str, context: SkillContext) -> str:
        heading = re.search(r"^#\s+(.+)$", essay, flags=re.MULTILINE)
        if heading:
            return heading.group(1).strip()
        topic = context.options.get("topic") or context.message
        return f"Ship 30 essay: {topic[:60]}"
