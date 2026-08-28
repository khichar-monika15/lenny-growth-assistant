"""
Intent router for the agent layer.

Routing is rule-based on purpose. An LLM classifier would add a full model
round trip to every turn - painful on local Ollama - and would make routing
non-deterministic and hard to test. These patterns are high-precision: they
match explicit requests to write something, and anything else falls through to
the grounded answer skill, which is the safe default.

Trade-off documented in architecture.md.
"""
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern

from .skills.artifact import ArtifactSkill
from .skills.base import Skill
from .skills.grounded_answer import GroundedAnswerSkill
from .skills.ship30 import Ship30Skill

logger = logging.getLogger(__name__)


def _compile(patterns: List[str]) -> List[Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


#: Explicit requests for a Ship 30 style essay.
SHIP30_PATTERNS = _compile([
    r"\bship\s*30\b",
    r"\batomic essay\b",
    r"\b(write|draft|generate|create|give me)\b[^.?!]{0,40}\b(essay|post|article|newsletter)\b",
    r"\bessay\b[^.?!]{0,30}\babout\b",
])

#: Requests that describe a document on their own, with or without prior turns.
ARTIFACT_PATTERNS = _compile([
    # A making verb plus a document noun and its subject.
    r"\b(write|draft|generate|create|build|make|put together|give me)\b[^.?!]{0,50}"
    r"\b(document|doc|one[- ]pager|onepager|checklist|template|table|summary sheet|"
    r"cheat ?sheet|playbook|brief|outline|report|page|landing page|mockup|"
    r"web ?page|site)\b",
    # A named format with its own subject: "an HTML page showing the tiers".
    r"\b(html|markdown)\b[^.?!]{0,25}\b(page|snippet|doc|document|file)\b"
    r"[^.?!]{0,40}\b(about|for|showing|of|on|with)\b",
])

#: Requests that only mean something as a follow-up, because they refer to
#: whatever was just produced: "make it html", "can you create an html version".
#: Routing these without prior turns would ask the model to convert nothing.
FOLLOWUP_ARTIFACT_PATTERNS = _compile([
    r"\b(convert|turn|render|export|reformat|rewrite)\b[^.?!]{0,40}\b(html|markdown|css)\b",
    r"\b(html|markdown)\b[^.?!]{0,25}\b(version|format|file|output)\b",
    r"\b(as|in|to|into)\b\s+(an?\s+)?(markdown|html)\b",
    r"\b(make|do|give me) (it|that|this)\b[^.?!]{0,20}\b(html|markdown)\b",
    r"\b(create|make|build|generate|give me)\b[^.?!]{0,30}\b(html|markdown)\b",
])


@dataclass
class Route:
    """The chosen skill and why it was chosen."""
    skill: Skill
    intent: str
    reason: str
    options: Dict[str, object]


class AgentRouter:
    """Classifies a message and dispatches it to the owning skill."""

    def __init__(self) -> None:
        self._ship30 = Ship30Skill()
        self._artifact = ArtifactSkill()
        self._grounded = GroundedAnswerSkill()
        self._by_name: Dict[str, Skill] = {
            skill.name: skill for skill in (self._ship30, self._artifact, self._grounded)
        }

    @property
    def skills(self) -> List[Skill]:
        return list(self._by_name.values())

    def get(self, name: str) -> Skill:
        """Fetch a skill by name for endpoints that address one directly."""
        try:
            return self._by_name[name]
        except KeyError:
            raise ValueError(f"Unknown skill: {name}") from None

    def route(
        self,
        message: str,
        forced_skill: Optional[str] = None,
        has_history: bool = False,
    ) -> Route:
        """
        Pick the skill for a message.

        Args:
            message: The user's message
            forced_skill: Skill name to use instead of classifying, for
                endpoints that target a skill explicitly
            has_history: Whether the session already has prior turns. Some
                requests only mean something as a follow-up, so they are
                matched only when there is something to refer back to.

        Returns:
            The selected Route
        """
        if forced_skill:
            skill = self.get(forced_skill)
            return Route(skill, skill.name, "explicitly requested", {})

        text = message.strip()

        if match := self._first_match(SHIP30_PATTERNS, text):
            return Route(
                self._ship30,
                self._ship30.name,
                f"matched essay request: {match!r}",
                {"topic": self._extract_topic(text)},
            )

        if match := self._first_match(ARTIFACT_PATTERNS, text):
            return Route(
                self._artifact,
                self._artifact.name,
                f"matched document request: {match!r}",
                {"format": ArtifactSkill.detect_format(text)},
            )

        if has_history and (match := self._first_match(FOLLOWUP_ARTIFACT_PATTERNS, text)):
            return Route(
                self._artifact,
                self._artifact.name,
                f"matched follow-up format request: {match!r}",
                {"format": ArtifactSkill.detect_format(text)},
            )

        return Route(self._grounded, self._grounded.name, "default", {})

    @staticmethod
    def _first_match(patterns: List[Pattern[str]], text: str) -> Optional[str]:
        for pattern in patterns:
            found = pattern.search(text)
            if found:
                return found.group(0)
        return None

    @staticmethod
    def _extract_topic(message: str) -> str:
        """
        Pull the subject out of "write an essay about X" so retrieval targets X.

        The separator may be a colon ("essay about: X"), which is how the
        Ship 30 endpoint phrases its own synthesised prompt. Missing that made
        the whole sentence the topic, which both weakened retrieval and
        produced titles like "Ship 30 essay: Write a Ship 30 essay about: X".
        """
        match = re.search(
            r"\b(?:about|on|covering|regarding|titled)\b\s*:?\s+(.+)",
            message,
            re.IGNORECASE,
        )
        if match:
            topic = match.group(1).strip(" .?!\"'")
            if topic:
                return topic
        return message
