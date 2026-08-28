"""Fetch transcripts from Lenny's public podcast transcript repository."""
import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


class TranscriptSourceError(RuntimeError):
    """Raised when the transcript repository cannot be read."""


class GitHubFetcher:
    """Fetch transcript files from GitHub raw content."""

    REPO_OWNER = "LennysNewsletter"
    REPO_NAME = "lennys-newsletterpodcastdata"
    BRANCH = "main"
    INDEX_PATH = "index.json"

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        self.client = httpx.AsyncClient(timeout=60.0, transport=transport)
        self.base_url = (
            f"https://raw.githubusercontent.com/{self.REPO_OWNER}/{self.REPO_NAME}/{self.BRANCH}"
        )

    async def fetch_index(self) -> List[Dict[str, Any]]:
        """
        Fetch index.json and return the podcast entries.

        The index is an object with schema_version/generated_at/podcasts/
        newsletters; only the podcast entries carry transcripts.
        """
        payload = (await self._get(self.INDEX_PATH)).json()
        podcasts = payload.get("podcasts", [])

        if not podcasts:
            raise TranscriptSourceError("Transcript index contained no podcast entries")

        return podcasts

    async def fetch_transcript(self, file_path: str) -> str:
        """Fetch an individual transcript markdown file."""
        return (await self._get(file_path.lstrip("/"))).text

    async def _get(self, path: str) -> httpx.Response:
        url = f"{self.base_url}/{path}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise TranscriptSourceError(
                f"Transcript repository returned HTTP {exc.response.status_code} for {path}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TranscriptSourceError(f"Cannot reach transcript repository: {exc}") from exc

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
