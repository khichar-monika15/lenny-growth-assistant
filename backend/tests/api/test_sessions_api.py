"""
Session API and persistence tests.

Persistence is a stated requirement and was entirely missing: session_id was
accepted and ignored, and no message was ever written. These tests pin the
contract end to end against the real database.
"""
import pytest

from tests.conftest import requires_db

pytestmark = requires_db


async def create_session(client) -> str:
    response = await client.post("/api/v1/sessions", json={})
    assert response.status_code == 201
    return response.json()["id"]


class TestSessionLifecycle:
    async def test_create_returns_a_session(self, client):
        response = await client.post("/api/v1/sessions", json={})

        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["is_active"] is True
        assert body["created_at"]

        await client.delete(f"/api/v1/sessions/{body['id']}")

    async def test_created_session_appears_in_the_list(self, client):
        session_id = await create_session(client)

        listed = await client.get("/api/v1/sessions")

        assert session_id in [s["id"] for s in listed.json()]
        await client.delete(f"/api/v1/sessions/{session_id}")

    async def test_delete_removes_the_session(self, client):
        session_id = await create_session(client)

        deleted = await client.delete(f"/api/v1/sessions/{session_id}")
        after = await client.get(f"/api/v1/sessions/{session_id}")

        assert deleted.status_code == 204
        assert after.status_code == 404

    async def test_unknown_session_returns_structured_404(self, client):
        response = await client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        assert response.json()["detail"]["error"] == "session_not_found"

    async def test_malformed_id_is_rejected_before_the_database(self, client):
        assert (await client.get("/api/v1/sessions/not-a-uuid")).status_code == 422


class TestMessagePersistence:
    async def test_turns_are_written_with_their_citations(self, client, monkeypatch):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        provider = FakeProvider("Grounded reply.")
        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=provider, name="ollama", model="test", requested="ollama"
            ),
        )

        session_id = await create_session(client)
        await client.post(
            "/api/v1/chat", json={"message": "What is PMF?", "session_id": session_id}
        )

        history = (await client.get(f"/api/v1/sessions/{session_id}/messages")).json()

        assert [m["role"] for m in history] == ["user", "assistant"]
        assert history[0]["content"] == "What is PMF?"
        assert history[1]["content"] == "Grounded reply."
        assert history[1]["token_count"] == 20
        assert history[1]["model_provider"] == "ollama"

        await client.delete(f"/api/v1/sessions/{session_id}")

    async def test_deleting_a_session_cascades_to_messages(self, client, db, monkeypatch):
        from sqlalchemy import func, select

        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.models import Message
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider(), name="ollama", model="test", requested="ollama"
            ),
        )

        session_id = await create_session(client)
        await client.post("/api/v1/chat", json={"message": "hi", "session_id": session_id})
        await client.delete(f"/api/v1/sessions/{session_id}")

        remaining = await db.execute(
            select(func.count()).select_from(Message).where(Message.session_id == session_id)
        )

        assert remaining.scalar_one() == 0

    async def test_session_is_titled_from_its_first_message(self, client, monkeypatch):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider(), name="ollama", model="test", requested="ollama"
            ),
        )

        session_id = await create_session(client)
        await client.post(
            "/api/v1/chat",
            json={"message": "How do I find product-market fit?", "session_id": session_id},
        )

        session = (await client.get(f"/api/v1/sessions/{session_id}")).json()

        assert session["title"].startswith("How do I find product-market fit")
        await client.delete(f"/api/v1/sessions/{session_id}")


class TestSessionIsolation:
    async def test_each_session_keeps_its_own_context(self, client, monkeypatch):
        """The requirement is independent context per session, not a shared thread."""
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        provider = FakeProvider()
        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=provider, name="ollama", model="test", requested="ollama"
            ),
        )

        first = await create_session(client)
        second = await create_session(client)

        await client.post("/api/v1/chat", json={"message": "first topic", "session_id": first})
        await client.post("/api/v1/chat", json={"message": "second topic", "session_id": second})

        # The second session's prompt must not replay the first session's turn.
        replayed = " ".join(m["content"] for m in provider.received_messages)
        assert "first topic" not in replayed

        second_history = (await client.get(f"/api/v1/sessions/{second}/messages")).json()
        assert len(second_history) == 2

        await client.delete(f"/api/v1/sessions/{first}")
        await client.delete(f"/api/v1/sessions/{second}")

    async def test_prior_turns_are_replayed_within_a_session(self, client, monkeypatch):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        provider = FakeProvider()
        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=provider, name="ollama", model="test", requested="ollama"
            ),
        )

        session_id = await create_session(client)
        await client.post(
            "/api/v1/chat", json={"message": "Tell me about PMF", "session_id": session_id}
        )
        await client.post(
            "/api/v1/chat", json={"message": "Why does that matter?", "session_id": session_id}
        )

        replayed = " ".join(m["content"] for m in provider.received_messages)
        assert "Tell me about PMF" in replayed

        await client.delete(f"/api/v1/sessions/{session_id}")


class TestChatContract:
    async def test_chat_creates_a_session_when_none_is_given(self, client, monkeypatch):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider(), name="ollama", model="test", requested="ollama"
            ),
        )

        response = await client.post("/api/v1/chat", json={"message": "hello"})

        assert response.status_code == 200
        body = response.json()
        assert body["session_id"]
        assert body["intent"] == "grounded_answer"
        assert body["provider"] == "ollama"

        await client.delete(f"/api/v1/sessions/{body['session_id']}")

    @pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 9000}])
    async def test_invalid_payloads_are_rejected(self, client, payload):
        assert (await client.post("/api/v1/chat", json=payload)).status_code == 422

    async def test_model_failures_return_a_typed_error_not_a_stack_trace(
        self, client, monkeypatch
    ):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.llm.providers.base import LLMUnavailable
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider(fail_with=LLMUnavailable("Ollama is down")),
                name="ollama",
                model="test",
                requested="ollama",
            ),
        )

        response = await client.post("/api/v1/chat", json={"message": "hello"})

        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "model_unavailable"
        assert "Traceback" not in response.text


class TestStreaming:
    async def test_stream_emits_ordered_events_and_always_terminates(self, client, monkeypatch):
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider("streamed reply"), name="ollama", model="t", requested="ollama"
            ),
        )

        async with client.stream(
            "POST", "/api/v1/chat/stream", json={"message": "hello"}
        ) as response:
            body = "".join([chunk async for chunk in response.aiter_text()])

        assert '"type": "session"' in body
        assert '"type": "sources"' in body
        assert '"type": "content_delta"' in body
        assert body.rstrip().endswith("[DONE]")

    async def test_stream_reports_errors_and_still_sends_done(self, client, monkeypatch):
        """A failed stream must not leave the client waiting forever."""
        from tests.conftest import FakeProvider
        from app.llm import factory
        from app.llm.providers.base import LLMTimeout
        from app.services import chat_service

        monkeypatch.setattr(
            chat_service,
            "resolve_provider",
            lambda requested=None: factory.ResolvedProvider(
                provider=FakeProvider(fail_with=LLMTimeout("too slow")),
                name="ollama",
                model="t",
                requested="ollama",
            ),
        )

        async with client.stream(
            "POST", "/api/v1/chat/stream", json={"message": "hello"}
        ) as response:
            body = "".join([chunk async for chunk in response.aiter_text()])

        assert '"type": "error"' in body
        assert "model_timeout" in body
        assert body.rstrip().endswith("[DONE]")


class TestHealth:
    async def test_liveness(self, client):
        assert (await client.get("/health")).json()["status"] == "healthy"

    async def test_database_health(self, client):
        assert (await client.get("/health/db")).json()["postgres"] == "available"

    async def test_llm_health_reports_both_providers(self, client):
        body = (await client.get("/health/llm")).json()

        assert "ollama" in body
        assert "anthropic" in body
