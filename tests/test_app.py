import json

from fastapi.testclient import TestClient
import httpx

from app import main as main_module


client = TestClient(main_module.app)


def test_index_is_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Gemma Pi Local" in response.text


def test_status_reports_mocked_litert(monkeypatch) -> None:
    async def fake_models():
        return True, [{"id": "gemma4-e4b"}], None

    async def fake_search_status():
        return True, None

    monkeypatch.setattr(main_module, "_litert_models", fake_models)
    monkeypatch.setattr(main_module, "_search_status", fake_search_status)
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["app"] == "ok"
    assert payload["litert"]["ok"] is True
    assert payload["litert"]["models"][0]["id"] == "gemma4-e4b"
    assert payload["search"]["ok"] is True
    assert "memory" in payload["system"]


def test_chat_rejects_invalid_model_identifier() -> None:
    response = client.post(
        "/api/chat",
        json={"model": "../../bad", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid model identifier"


def test_chat_rejects_remote_image_url() -> None:
    response = client.post(
        "/api/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/private.png"},
                        },
                        {"type": "text", "text": "describe"},
                    ],
                }
            ]
        },
    )
    assert response.status_code == 400
    assert "inline" in response.json()["error"]


def test_chat_returns_direct_planner_text(monkeypatch) -> None:
    real_async_client = httpx.AsyncClient

    def upstream(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert payload["model"] == "gemma4-e4b"
        assert payload["stream"] is False
        assert payload["max_completion_tokens"] == 32
        assert payload["tools"][0]["function"]["name"] == "web_search"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "local"}}]}
        )

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(upstream)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(main_module.httpx, "AsyncClient", client_factory)
    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"content":"local"' in response.text
    assert "data: [DONE]" in response.text


def test_chat_runs_one_search_and_streams_cited_answer(monkeypatch) -> None:
    real_async_client = httpx.AsyncClient
    completion_count = 0

    class EventStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield (
                'data: {"choices":[{"delta":{"content":"Current answer [1]."}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode()

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal completion_count
        if request.url.port == 8888:
            assert request.method == "GET"
            assert request.url.path == "/search"
            assert request.url.params["q"] == "current Raspberry Pi OS release"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Raspberry Pi OS",
                            "url": "https://www.raspberrypi.com/software/",
                            "content": "Current release information.",
                            "engines": ["duckduckgo"],
                        }
                    ]
                },
            )

        completion_count += 1
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        if completion_count == 1:
            assert payload["stream"] is False
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_search_1",
                                        "type": "function",
                                        "function": {
                                            "name": "web_search",
                                            "arguments": json.dumps(
                                                {
                                                    "query": "current Raspberry Pi OS release"
                                                }
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )

        assert completion_count == 2
        assert payload["stream"] is True
        assert "tools" not in payload
        assert payload["messages"][-2]["role"] == "assistant"
        assert payload["messages"][-1]["role"] == "tool"
        assert payload["messages"][-1]["tool_call_id"] == "call_search_1"
        assert "[1] Raspberry Pi OS" in payload["messages"][-1]["content"]
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=EventStream(),
        )

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(upstream)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(main_module.httpx, "AsyncClient", client_factory)
    response = client.post(
        "/api/chat",
        json={
            "messages": [
                {"role": "user", "content": "What is the current Raspberry Pi OS?"}
            ],
            "max_tokens": 64,
        },
    )
    assert response.status_code == 200
    assert completion_count == 2
    assert '"type":"search"' in response.text
    assert '"number":1' in response.text
    assert "https://www.raspberrypi.com/software/" in response.text
    assert "Current answer [1]." in response.text


def test_chat_rejects_malformed_tool_call(monkeypatch) -> None:
    real_async_client = httpx.AsyncClient

    def upstream(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "bad call id",
                                    "type": "function",
                                    "function": {
                                        "name": "web_search",
                                        "arguments": "{}",
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(upstream)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(main_module.httpx, "AsyncClient", client_factory)
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "search"}]},
    )
    assert response.status_code == 502
    assert response.json()["error"] == "Gemma tool planning failed"
