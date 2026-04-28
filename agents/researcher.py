"""
researcher.py — Web Research Agent
Uses DuckDuckGo search + httpx + BeautifulSoup to find and summarize information.
"""

import logging
import asyncio

logger = logging.getLogger(__name__)

# Lazy imports — these packages may be heavy
_ddg = None
_httpx = None
_bs4 = None


def _get_ddg():
    global _ddg
    if _ddg is None:
        from duckduckgo_search import DDGS
        _ddg = DDGS
    return _ddg


def _get_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


def _get_bs4():
    global _bs4
    if _bs4 is None:
        from bs4 import BeautifulSoup
        _bs4 = BeautifulSoup
    return _bs4


from .base_agent import BaseAgent


class ResearcherAgent(BaseAgent):
    """Agent that searches the web and summarizes findings."""

    def __init__(self):
        super().__init__(
            name="Researcher",
            description="Searches the web and summarizes findings",
        )

    async def execute(self, task: str, context: dict = None) -> str:
        """Search the web for the given query and return summarized results."""
        logger.info(f"[Researcher] Searching for: {task[:80]}")

        try:
            results = await self.search(task, max_results=5)
        except Exception as e:
            logger.error(f"[Researcher] search failed: {e}", exc_info=True)
            return f"❌ Search failed: {e}"

        if not results:
            return "🔍 No results found for that query."

        # Format results
        lines = [f"**🔍 Search Results for:** `{task}`\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            body = r.get("body", "")[:200]
            href = r.get("href", "")
            lines.append(f"**{i}.** [{title}]({href})")
            if body:
                lines.append(f"> {body}\n")

        response = "\n".join(lines)
        logger.info(f"[Researcher] Found {len(results)} results")
        return response

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Run a DuckDuckGo text search in a thread (sync library)."""
        DDGS = _get_ddg()

        def _sync_search():
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        results = await asyncio.to_thread(_sync_search)
        return results

    async def fetch_page(self, url: str) -> str:
        """Fetch a web page and extract clean text."""
        httpx = _get_httpx()
        BeautifulSoup = _get_bs4()

        logger.info(f"[Researcher] Fetching page: {url}")
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            # Truncate to reasonable length
            return text[:3000]

        except Exception as e:
            logger.error(f"[Researcher] fetch_page failed: {e}", exc_info=True)
            return f"Failed to fetch page: {e}"
