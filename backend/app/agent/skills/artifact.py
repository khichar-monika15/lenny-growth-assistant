"""
Artifact skill: produce a standalone Markdown or HTML document.

The document is returned as a typed artifact so the frontend can render it in
the viewer beside the chat rather than dumping a code block into the thread.
HTML is treated as untrusted all the way through: this skill constrains what
the model may emit, and the viewer independently sanitises and sandboxes it.
"""
import re
from typing import ClassVar, Optional

from .base import Artifact, Skill, SkillContext, SkillPlan, SkillResult

MARKDOWN_TRIGGERS = ("markdown", "md", "doc", "document", "checklist", "outline", "brief")
HTML_TRIGGERS = ("html", "css", "web page", "webpage", "landing page", "mockup")

_FENCE = re.compile(r"```(?:html|markdown|md)?\s*\n(.*?)```", re.DOTALL)

COMMON_RULES = """Base every factual claim on the transcript excerpts below and
attribute borrowed ideas to the guest by name. If the excerpts do not cover
something, leave it out rather than inventing it.

TRANSCRIPT EXCERPTS
{context}"""

MARKDOWN_PROMPT = """You produce standalone Markdown documents for a product and
growth team.

Write a well-structured document with a single H1 title, descriptive H2
sections, and lists or tables wherever they carry the content better than
prose. Keep it skimmable and specific.

{common}

Output only the Markdown document. No preamble and no code fence."""

HTML_PROMPT = """You produce standalone HTML documents for a product and growth
team.

Write a complete, self-contained HTML fragment with an inline <style> block.
The renderer sanitises output and runs it in a sandboxed frame with scripting
disabled, so:
- No <script>, no event handler attributes, no javascript: URLs. They are
  stripped before rendering and will simply vanish.
- No external requests: no <link>, no remote fonts, images or stylesheets.
- Layout and styling only. Anything interactive will not run.

Use semantic elements and readable typography.

{common}

Output only the HTML. No preamble and no code fence."""


class ArtifactSkill(Skill):
    """Generates a Markdown or HTML artifact from the conversation."""

    name: ClassVar[str] = "artifact"
    description: ClassVar[str] = (
        "Produce a Markdown or HTML/CSS document rendered in the artifact viewer"
    )
    retrieval_top_k: ClassVar[Optional[int]] = 12

    @staticmethod
    def detect_format(message: str) -> str:
        """Pick the output format from the request wording. Markdown is the default."""
        lowered = message.lower()
        if any(trigger in lowered for trigger in HTML_TRIGGERS):
            return "html"
        return "markdown"

    def plan(self, context: SkillContext) -> SkillPlan:
        artifact_format = context.options.get("format") or self.detect_format(context.message)
        assembled = context.assembled
        excerpts = assembled.context if assembled and not assembled.is_empty else ""
        common = COMMON_RULES.format(context=excerpts)
        template = HTML_PROMPT if artifact_format == "html" else MARKDOWN_PROMPT

        return SkillPlan(
            system_prompt=template.format(common=common),
            messages=[*context.history, {"role": "user", "content": context.message}],
            max_tokens=4096,
            temperature=0.5,
        )

    def finalize(self, text: str, context: SkillContext) -> SkillResult:
        artifact_format = context.options.get("format") or self.detect_format(context.message)
        content = self._unfence(text)
        title = self._title(content, artifact_format, context)

        return SkillResult(
            content=content,
            artifact=Artifact(type=artifact_format, title=title, content=content),
            metadata={"format": artifact_format},
        )

    @staticmethod
    def _unfence(text: str) -> str:
        """Models wrap output in a code fence despite instructions; unwrap it."""
        match = _FENCE.search(text.strip())
        return match.group(1).strip() if match else text.strip()

    @staticmethod
    def _title(content: str, artifact_format: str, context: SkillContext) -> str:
        if artifact_format == "html":
            match = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
        else:
            match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)

        if match:
            return re.sub(r"<[^>]+>", "", match.group(1)).strip()[:120]
        return context.message[:60]
