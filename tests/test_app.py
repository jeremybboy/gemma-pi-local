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

    monkeypatch.setattr(main_module, "_litert_models", fake_models)
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["app"] == "ok"
    assert payload["litert"]["ok"] is True
    assert payload["litert"]["models"][0]["id"] == "gemma4-e4b"
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


def test_chat_proxies_stream_from_litert(monkeypatch) -> None:
    real_async_client = httpx.AsyncClient

    class EventStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield (
                'data: {"choices":[{"delta":{"content":"local"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode()

    def upstream(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert payload["model"] == "gemma4-e4b"
        assert payload["stream"] is True
        assert payload["max_completion_tokens"] == 32
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
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"content":"local"' in response.text
    assert "data: [DONE]" in response.text
