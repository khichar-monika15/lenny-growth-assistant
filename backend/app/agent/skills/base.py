"""
Skill contract for the agent layer.

A skill owns one job: what to retrieve for it, how to prompt for it, and how to
turn the model's raw text into a result. Orchestration (retrieval, streaming,
persistence) stays in ChatService so every skill streams and persists
identically and skills stay independently testable.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from app.rag.context_assembler import AssembledContext


@dataclass
class SkillContext:
    """Everything a skill needs to build its request."""
    message: str
    history: List[Dict[str, str]] = field(default_factory=list)
    assembled: Optional[AssembledContext] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillPlan:
    """A skill's instructions for the provider."""
    system_prompt: str
    messages: List[Dict[str, str]]
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class Artifact:
    """A rendered document produced alongside the reply."""
    type: str  # "markdown" | "html"
    title: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type, "title": self.title, "content": self.content}


@dataclass
class SkillResult:
    """A skill's finished output."""
    content: str
    artifact: Optional[Artifact] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Skill(ABC):
    """Base class for agent skills."""

    name: ClassVar[str]
    description: ClassVar[str]
    #: Skills that produce a long document need a bigger retrieval window.
    retrieval_top_k: ClassVar[Optional[int]] = None

    def retrieval_query(self, context: SkillContext) -> str:
        """Text to embed when searching the transcript index."""
        return context.message

    @abstractmethod
    def plan(self, context: SkillContext) -> SkillPlan:
        """Build the provider request."""

    def finalize(self, text: str, context: SkillContext) -> SkillResult:
        """Turn raw model output into a result."""
        return SkillResult(content=text)
