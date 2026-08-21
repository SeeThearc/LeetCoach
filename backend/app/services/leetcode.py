"""
LeetCode API client.

Fetches problem data from your API at leetcode-api-pied.vercel.app.
Uses httpx for async HTTP requests and a simple in-memory cache
so we don't fetch the same problem twice.
"""

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Simple cache: {"two-sum": {problem_data}, "valid-parentheses": {problem_data}}
# Lives as long as the server is running. Restart clears it.
_cache: dict[str, dict] = {}


async def fetch_problem(slug: str) -> dict:
    """Fetch problem data from the LeetCode API.

    Args:
        slug: Problem slug like "two-sum" or problem ID like "1"

    Returns:
        Dict with problem data: title, content, difficulty, topicTags, etc.

    Raises:
        NotFoundError: If the problem doesn't exist
        ExternalServiceError: If the API is down or returns an error
    """
    # Check cache first
    if slug in _cache:
        logger.info("Cache hit", slug=slug)
        return _cache[slug]

    settings = get_settings()
    url = f"{settings.leetcode_api_base_url}/problem/{slug}"

    logger.info("Fetching problem from API", slug=slug, url=url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)

            # Problem not found
            if response.status_code == 404:
                raise NotFoundError("Problem", slug)

            # Any other error
            response.raise_for_status()

            data = response.json()

    except NotFoundError:
        raise  # Re-raise our own error
    except httpx.TimeoutException:
        raise ExternalServiceError("LeetCode API", "Request timed out")
    except httpx.HTTPError as e:
        raise ExternalServiceError("LeetCode API", str(e))

    # Cache it
    _cache[slug] = data
    logger.info("Problem fetched and cached", slug=slug, title=data.get("title"))

    return data


async def search_problems(query: str) -> list[dict]:
    """Search for problems by keyword.

    Args:
        query: Search query like "two sum" or "binary tree"

    Returns:
        List of matching problems
    """
    settings = get_settings()
    url = f"{settings.leetcode_api_base_url}/search"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"query": query}, timeout=10.0)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise ExternalServiceError("LeetCode API", str(e))
