"""Local web-search boundary for Gemma Pi Local."""

from app.search.searxng import (
    SearchError,
    SearchResult,
    SearXNGClient,
    render_search_evidence,
)

__all__ = [
    "SearchError",
    "SearchResult",
    "SearXNGClient",
    "render_search_evidence",
]
