import json

import httpx
import pytest

from app.search import SearchError, SearchResult, SearXNGClient, render_search_evidence


@pytest.mark.asyncio
async def test_search_normalizes_bounds_and_deduplicates_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "Raspberry Pi Gemma"
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "  First   result ",
                        "url": "https://example.com/one",
                        "content": " useful   snippet ",
                        "engines": ["duckduckgo", "brave"],
                    },
                    {
                        "title": "duplicate",
                        "url": "https://example.com/one",
                        "content": "ignored",
                    },
                    {"title": "unsafe", "url": "file:///etc/passwd"},
                    {
                        "title": "credential URL",
                        "url": "https://user:password@example.net/private",
                    },
                    {
                        "title": "Second result",
                        "url": "http://example.org/two",
                        "content": "second snippet",
                        "engine": "wikipedia",
                    },
                ]
            },
        )

    client = SearXNGClient(
        "http://127.0.0.1:8888",
        max_results=2,
        transport=httpx.MockTransport(handler),
    )
    results = await client.search("  Raspberry   Pi Gemma  ")

    assert results == [
        SearchResult(
            title="First result",
            url="https://example.com/one",
            snippet="useful snippet",
            engines=("duckduckgo", "brave"),
        ),
        SearchResult(
            title="Second result",
            url="http://example.org/two",
            snippet="second snippet",
            engines=("wikipedia",),
        ),
    ]


@pytest.mark.asyncio
async def test_search_rejects_bad_response() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=b"[]"))
    client = SearXNGClient("http://localhost:8888", transport=transport)
    with pytest.raises(SearchError, match="invalid JSON response"):
        await client.search("test")


@pytest.mark.asyncio
async def test_search_health_requires_successful_loopback_response() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, text="ready"))
    client = SearXNGClient("http://127.0.0.1:8888", transport=transport)
    await client.health()


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:8888",
        "http://192.168.68.66:8888",
        "http://example.com",
        "http://user:password@localhost:8888",
    ],
)
def test_search_rejects_non_loopback_service(base_url: str) -> None:
    with pytest.raises(ValueError, match="loopback|credentials"):
        SearXNGClient(base_url)


def test_search_evidence_has_stable_source_numbers() -> None:
    evidence = render_search_evidence(
        "current info",
        [
            SearchResult("One", "https://one.example", "First", ("brave",)),
            SearchResult("Two", "https://two.example", "Second", ()),
        ],
    )
    assert "untrusted search evidence" in evidence
    assert "[1] One (brave)" in evidence
    assert "[2] Two" in evidence
    assert evidence.index("[1]") < evidence.index("[2]")


def test_search_query_is_bounded() -> None:
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, content=json.dumps({"results": []}).encode())

    client = SearXNGClient(
        "http://127.0.0.1:8888",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ValueError, match="exceeds"):
        render_search_evidence("x" * 301, [])
    assert request_count == 0
