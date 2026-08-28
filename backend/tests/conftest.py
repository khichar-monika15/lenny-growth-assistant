"""
Shared fixtures.

API tests run against the real PostgreSQL instance from docker compose rather
than a stub, because the behaviour worth testing here - cascade deletes,
JSONB round-tripping, the reserved `metadata` column mapping - only exists in
the real database.
"""
import asyncio
import logging
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.database import AsyncSessionLocal, engine
from app.main import app

# The pool logs a GC warning per connection at interpreter shutdown, after
# pytest has closed its capture streams. Harmless, but it buries the summary.
logging.getLogger("sqlalchemy.pool").setLevel(logging.CRITICAL)


def _database_reachable() -> bool:
    async def check() -> bool:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            # Leave no pooled connection behind: it belongs to this throwaway
            # loop and would be handed to a test running on a different one.
            await engine.dispose()

    return asyncio.run(check())


requires_db = pytest.mark.skipif(
    not _database_reachable(),
    reason="PostgreSQL is not reachable; start it with: docker compose up -d postgres",
)


@pytest_asyncio.fixture(autouse=True)
async def _isolate_engine_per_loop() -> AsyncIterator[None]:
    """
    Dispose the pool around every test.

    The engine is created once at import, but pytest-asyncio runs each test on
    a fresh event loop. A pooled asyncpg connection carries its loop with it,
    so reusing one across tests raises "attached to a different loop".
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncIterator:
    """A database session that rolls nothing back; tests clean up their own rows."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP client bound to the ASGI app, no network listener required."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


class FakeProvider:
    """Deterministic stand-in for an LLM, so API tests do not need a model."""

    def __init__(self, text: str = "A grounded answer.", *, fail_with: Exception | None = None):
        self.text = text
        self.fail_with = fail_with
        self.received_messages: list[dict] = []
        self.received_system: str | None = None
        self.closed = False

    async def generate(self, messages, system_prompt=None, max_tokens=2048, temperature=0.7, **_):
        if self.fail_with:
            raise self.fail_with
        self.received_messages = messages
        self.received_system = system_prompt
        return {
            "content": self.text,
            "stop_reason": "stop",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    async def stream(self, messages, system_prompt=None, max_tokens=2048, temperature=0.7, **_):
        if self.fail_with:
            raise self.fail_with
        self.received_messages = messages
        self.received_system = system_prompt
        for word in self.text.split():
            yield {"type": "content_delta", "delta": word + " "}
        yield {"type": "message_stop", "usage": {"input_tokens": 10, "output_tokens": 20}}

    async def count_tokens(self, text: str) -> int:
        return len(text.split())

    async def aclose(self) -> None:
        self.closed = True
