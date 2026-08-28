"""Ship 30 skill tests: the encoded rules and the word-count contract."""
import pytest

from app.agent.skills.base import SkillContext
from app.agent.skills.ship30 import (
    DEFAULT_WORD_COUNT,
    FORMATTING_RULES,
    HOOK_STYLES,
    WRITING_PRINCIPLES,
    Ship30Skill,
    build_system_prompt,
    completion_tokens,
    count_words,
    target_sections,
    within_tolerance,
)
from app.rag.context_assembler import AssembledContext


@pytest.fixture
def skill() -> Ship30Skill:
    return Ship30Skill()


def context_with(**options) -> SkillContext:
    return SkillContext(
        message="Write an essay about retention",
        assembled=AssembledContext(context="[Source 1: Ep] Retention compounds.", total_chunks=1),
        options=options,
    )


class TestWordCountContract:
    def test_default_matches_the_brief(self):
        assert DEFAULT_WORD_COUNT == 1250

    def test_token_budget_can_hold_the_essay(self):
        """A 1250-word essay needs well over the old 1500-token ceiling."""
        assert completion_tokens(1250) >= 2500

    def test_token_budget_scales_with_target(self):
        assert completion_tokens(1250) > completion_tokens(250)

    @pytest.mark.parametrize(
        "actual,target,expected",
        [
            (1250, 1250, True),
            (1180, 1250, True),
            (1320, 1250, True),
            (600, 1250, False),
            (2000, 1250, False),
            (250, 250, True),
            (100, 250, False),
        ],
    )
    def test_tolerance_band(self, actual, target, expected):
        assert within_tolerance(actual, target) is expected

    def test_word_count_ignores_markdown_syntax(self):
        assert count_words("# Title\n\n**bold** word") == count_words("Title bold word")

    def test_word_count_ignores_code_blocks(self):
        text = "Real words here\n\n```\nnot counted at all in here\n```"
        assert count_words(text) == 3


class TestStructure:
    @pytest.mark.parametrize(
        "words,expected", [(250, 1), (500, 2), (1250, 5), (10000, 6)]
    )
    def test_sections_scale_with_length(self, words, expected):
        assert target_sections(words) == expected

    def test_short_essays_still_get_a_section(self):
        assert target_sections(1) >= 1


class TestPromptComposition:
    def test_prompt_encodes_every_principle(self):
        prompt = build_system_prompt("retention", 1250, "question", "excerpt")

        for rule in WRITING_PRINCIPLES + FORMATTING_RULES:
            assert rule in prompt

    def test_prompt_carries_the_selected_hook_instruction(self):
        prompt = build_system_prompt("retention", 1250, "contrarian", "excerpt")

        assert HOOK_STYLES["contrarian"] in prompt
        assert HOOK_STYLES["stat"] not in prompt

    def test_prompt_states_the_word_target(self):
        assert "800 words" in build_system_prompt("x", 800, "question", "")

    def test_prompt_includes_the_retrieved_excerpts(self):
        assert "Retention compounds" in build_system_prompt(
            "x", 500, "question", "Retention compounds"
        )


class TestSkillBehaviour:
    def test_retrieval_uses_the_topic_not_the_raw_request(self, skill):
        query = skill.retrieval_query(context_with(topic="customer retention"))

        assert query == "customer retention"

    def test_plan_sizes_max_tokens_to_the_target(self, skill):
        plan = skill.plan(context_with(topic="retention", word_count=1250))

        assert plan.max_tokens >= 2500

    def test_finalize_returns_a_markdown_artifact(self, skill):
        result = skill.finalize("# Retention compounds\n\nBody text.", context_with(topic="x"))

        assert result.artifact is not None
        assert result.artifact.type == "markdown"
        assert result.artifact.title == "Retention compounds"

    def test_finalize_reports_the_measured_word_count(self, skill):
        result = skill.finalize("one two three four five", context_with(word_count=1250))

        assert result.metadata["word_count"] == 5
        assert result.metadata["within_tolerance"] is False

    def test_finalize_falls_back_to_topic_when_no_heading(self, skill):
        result = skill.finalize("No heading here.", context_with(topic="retention loops"))

        assert "retention loops" in result.artifact.title
