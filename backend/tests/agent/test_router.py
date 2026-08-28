"""
Routing tests.

Routing decides which skill answers, so a misroute is user-visible: an essay
request answered conversationally, or a question answered as a 1250-word
essay. Both directions are pinned here.
"""
import pytest

from app.agent.router import AgentRouter
from app.agent.skills.artifact import ArtifactSkill
from app.agent.skills.grounded_answer import GroundedAnswerSkill
from app.agent.skills.ship30 import Ship30Skill


@pytest.fixture
def router() -> AgentRouter:
    return AgentRouter()


class TestShip30Routing:
    @pytest.mark.parametrize(
        "message",
        [
            "Write a Ship 30 essay about product-market fit",
            "write me an essay about retention",
            "Draft a post about hiring senior engineers",
            "Can you generate an article about growth loops?",
            "I want an atomic essay on pricing",
            "ship30 essay on onboarding",
        ],
    )
    def test_essay_requests_route_to_ship30(self, router, message):
        assert router.route(message).intent == Ship30Skill.name


class TestArtifactRouting:
    @pytest.mark.parametrize(
        "message",
        [
            "Create a markdown checklist for enterprise sales calls",
            "Build me a one-pager on activation metrics",
            "Make an HTML page showing the pricing tiers",
            "Put together a template for user interviews",
        ],
    )
    def test_document_requests_route_to_artifact(self, router, message):
        assert router.route(message).intent == ArtifactSkill.name

FOLLOWUP_FORMAT_REQUESTS = [
    ("Can you create html version.", "html"),
    ("can you create an html version", "html"),
    ("convert this to html", "html"),
    ("turn that into html", "html"),
    ("make it html", "html"),
    ("export as html", "html"),
    ("give me a markdown version", "markdown"),
    ("render it as markdown", "markdown"),
    # "in markdown" refers to prior output, so this belongs here rather than
    # among the self-contained requests.
    ("Give me a summary in markdown", "markdown"),
]


class TestFollowUpFormatRequests:
    """
    "Make it html" refers to whatever was just produced.

    These used to fall through to a conversational answer, so the model wrote
    a code block into the thread instead of producing an artifact. They only
    match when the session has prior turns: with nothing to convert, the same
    words are better served by a normal answer.
    """

    @pytest.mark.parametrize("message,expected_format", FOLLOWUP_FORMAT_REQUESTS)
    def test_route_to_artifact_when_there_is_history(self, router, message, expected_format):
        route = router.route(message, has_history=True)

        assert route.intent == ArtifactSkill.name
        assert route.options["format"] == expected_format

    @pytest.mark.parametrize("message,_format", FOLLOWUP_FORMAT_REQUESTS)
    def test_stay_conversational_as_a_first_message(self, router, message, _format):
        assert router.route(message, has_history=False).intent == GroundedAnswerSkill.name

    @pytest.mark.parametrize(
        "message",
        [
            "Create a markdown checklist for a sales call",
            "Make an HTML page showing the pricing tiers",
            "Build me a one-pager on activation metrics",
        ],
    )
    def test_self_contained_requests_do_not_need_history(self, router, message):
        """A request that names its own subject stands alone."""
        assert router.route(message, has_history=False).intent == ArtifactSkill.name
        assert router.route(message, has_history=True).intent == ArtifactSkill.name


class TestDefaultRouting:
    @pytest.mark.parametrize(
        "message",
        [
            "What does Lenny say about product-market fit?",
            "How do I find my first ten customers?",
            "Why did that approach fail?",
            "Tell me about growth loops",
            "who is jen abel",
        ],
    )
    def test_questions_route_to_grounded_answer(self, router, message):
        assert router.route(message).intent == GroundedAnswerSkill.name

    def test_empty_message_falls_through_safely(self, router):
        assert router.route("").intent == GroundedAnswerSkill.name


class TestForcedSkill:
    def test_forced_skill_overrides_classification(self, router):
        route = router.route("What is PMF?", forced_skill=Ship30Skill.name)

        assert route.intent == Ship30Skill.name
        assert route.reason == "explicitly requested"

    def test_unknown_skill_is_rejected(self, router):
        with pytest.raises(ValueError, match="Unknown skill"):
            router.route("anything", forced_skill="does_not_exist")


class TestTopicExtraction:
    def test_topic_is_extracted_for_retrieval(self, router):
        route = router.route("Write an essay about customer retention loops")

        assert route.options["topic"] == "customer retention loops"

    def test_topic_falls_back_to_whole_message(self, router):
        route = router.route("Write a Ship 30 essay")

        assert route.options["topic"] == "Write a Ship 30 essay"

    @pytest.mark.parametrize(
        "message,expected",
        [
            ("Write a Ship 30 essay about: building talent density", "building talent density"),
            ("Write an essay on: pricing strategy", "pricing strategy"),
            ("Write an essay about retention loops.", "retention loops"),
        ],
    )
    def test_colon_separated_topics_are_extracted(self, router, message, expected):
        """The Ship 30 endpoint phrases its own prompt with a colon."""
        assert router.route(message).options["topic"] == expected


class TestFormatDetection:
    def test_html_request_selects_html(self, router):
        assert router.route("Build an HTML page for pricing").options["format"] == "html"

    def test_document_request_defaults_to_markdown(self, router):
        assert router.route("Create a checklist document").options["format"] == "markdown"


class TestRouteMetadata:
    def test_every_route_explains_itself(self, router):
        for message in ("What is PMF?", "Write an essay about PMF", "Make an HTML page"):
            assert router.route(message).reason

    def test_all_skills_are_addressable_by_name(self, router):
        for skill in router.skills:
            assert router.get(skill.name) is skill
