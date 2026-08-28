"""Fetch transcripts from Lenny's GitHub repo."""
import httpx
from typing import List, Dict, Any
from app.config import get_settings


class GitHubFetcher:
    """Fetch transcript files from GitHub."""

    REPO_OWNER = "LennysNewsletter"
    REPO_NAME = "lennys-newsletterpodcastdata"
    BRANCH = "main"
    INDEX_PATH = "index.json"
    TRANSCRIPT_BASE = ""

    def __init__(self):
        self.settings = get_settings()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.base_url = f"https://raw.githubusercontent.com/{self.REPO_OWNER}/{self.REPO_NAME}/{self.BRANCH}"

    async def fetch_index(self) -> List[Dict[str, Any]]:
        """Fetch index.json with all transcript metadata."""
        url = f"{self.base_url}/{self.INDEX_PATH}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def fetch_transcript(self, file_path: str) -> str:
        """Fetch individual transcript markdown file."""
        # Remove leading slash if present
        file_path = file_path.lstrip("/")
        url = f"{self.base_url}/{file_path}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.text

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
