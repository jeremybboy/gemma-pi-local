"""FastAPI gateway and static web UI for Gemma Pi Local."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.system_status import snapshot


MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
IMAGE_DATA_PATTERN = re.compile(
    r"^data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)$"
)
ALLOWED_ROLES = {"system", "user", "assistant"}
MAX_TEXT_CHARS = 40_000


class ChatRequest(BaseModel):
    """A constrained OpenAI-compatible chat request from the local UI."""

    model: str | None = None
    messages: list[dict[str, Any]]
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)


app = FastAPI(
    title="Gemma Pi Local",
    description="Local-only web gateway for LiteRT-LM on Raspberry Pi.",
    version="0.1.0",
)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject oversized uploads before parsing their JSON/base64 payload."""

    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            content_length = int(raw_length)
        except ValueError:
            return JSONResponse({"error": "Invalid Content-Length"}, status_code=400)
        if content_length > settings.max_request_bytes:
            return JSONResponse(
                {"error": "Request is larger than this device allows"},
                status_code=413,
            )
    return await call_next(request)


def _validate_base64(data: Any, label: str) -> None:
    if not isinstance(data, str) or not data:
        raise ValueError(f"{label} data is missing")
    approximate_size = len(data) * 3 // 4
    if approximate_size > settings.max_attachment_bytes:
        raise ValueError(f"{label} exceeds the attachment limit")
    try:
        base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{label} is not valid base64") from exc


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """Fail closed around the LiteRT-LM server's permissive request parser."""

    if not messages:
        raise ValueError("At least one message is required")
    if len(messages) > settings.max_messages:
        raise ValueError("Conversation is too long; start a new chat")

    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Every message must be an object")
        role = message.get("role")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Unsupported message role: {role!r}")
        content = message.get("content")
        if isinstance(content, str):
            if len(content) > MAX_TEXT_CHARS:
                raise ValueError("Message text is too long")
            continue
        if not isinstance(content, list) or not content:
            raise ValueError("Message content must be text or a non-empty list")

        image_count = 0
        audio_count = 0
        for part in content:
            if not isinstance(part, dict):
                raise ValueError("Message content parts must be objects")
            part_type = part.get("type")
            if part_type == "text":
                text = part.get("text")
                if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
                    raise ValueError("Invalid text content")
            elif part_type == "image_url":
                image_count += 1
                image_url = part.get("image_url")
                if not isinstance(image_url, dict):
                    raise ValueError("Invalid image content")
                match = IMAGE_DATA_PATTERN.fullmatch(str(image_url.get("url", "")))
                if not match:
                    raise ValueError("Images must be inline PNG, JPEG, or WebP data")
                _validate_base64(match.group(1).replace("\n", "").replace("\r", ""), "Image")
            elif part_type == "input_audio":
                audio_count += 1
                audio = part.get("input_audio")
                if not isinstance(audio, dict) or audio.get("format") != "wav":
                    raise ValueError("V0 accepts WAV audio only")
                _validate_base64(audio.get("data"), "Audio")
            else:
                raise ValueError(f"Unsupported content type: {part_type!r}")
        if image_count > 1 or audio_count > 1:
            raise ValueError("Each message can contain at most one image and one audio file")


async def _litert_models() -> tuple[bool, list[dict[str, Any]], str | None]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.litert_base_url}/models")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return False, [], str(exc)
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return True, models if isinstance(models, list) else [], None


@app.get("/api/status")
async def status() -> dict[str, Any]:
    litert_ok, models, error = await _litert_models()
    return {
        "app": "ok",
        "litert": {"ok": litert_ok, "models": models, "error": error},
        "default_model": settings.default_model,
        "system": snapshot(),
    }


@app.post("/api/chat")
async def chat(chat_request: ChatRequest):
    model = chat_request.model or settings.default_model
    if not MODEL_ID_PATTERN.fullmatch(model):
        return JSONResponse({"error": "Invalid model identifier"}, status_code=400)
    try:
        validate_messages(chat_request.messages)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    payload = {
        "model": model,
        "messages": chat_request.messages,
        "temperature": chat_request.temperature,
        "max_completion_tokens": chat_request.max_tokens,
        "stream": True,
    }
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=None, write=30.0, pool=5.0)
    )
    try:
        upstream = await client.send(
            client.build_request(
                "POST",
                f"{settings.litert_base_url}/chat/completions",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ),
            stream=True,
        )
    except httpx.HTTPError as exc:
        await client.aclose()
        return JSONResponse(
            {"error": "LiteRT-LM is unavailable", "detail": str(exc)},
            status_code=502,
        )

    if upstream.status_code >= 400:
        body = (await upstream.aread()).decode("utf-8", errors="replace")[:2000]
        await upstream.aclose()
        await client.aclose()
        return JSONResponse(
            {
                "error": "LiteRT-LM rejected the request",
                "upstream_status": upstream.status_code,
                "detail": body,
            },
            status_code=502,
        )

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


app.mount("/assets", StaticFiles(directory=settings.static_dir), name="assets")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")
