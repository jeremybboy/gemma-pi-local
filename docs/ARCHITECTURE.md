# Architecture

## Components

1. `static/` is an offline browser client built with plain HTML, CSS, and JavaScript. It holds the current tab's conversation and media previews in memory.
2. `app/` is a small FastAPI gateway. It serves the UI, validates requests, reports non-sensitive Pi health, and streams LiteRT-LM responses.
3. LiteRT-LM serves its OpenAI-compatible API on loopback and owns model loading and inference.
4. `bin/gemma-pi` controls the two processes and exposes status, logs, URL, and doctor commands.

## Multimodal request flow

The browser reads selected files locally, checks type and size, and converts them to base64. A user message is sent as OpenAI-compatible content parts in this order: image, audio, then text. The gateway validates the same constraints again and forwards the request to `/v1/chat/completions` with streaming enabled.

LiteRT-LM emits server-sent events. The gateway passes those bytes through without interpreting model text, and the browser appends text deltas to the assistant message until `[DONE]` arrives.

## Deliberate V0 boundaries

- One process group, one user, one active browser conversation.
- No accounts, database, cookies, analytics, telemetry, or cloud inference.
- No microphone capture or direct Behringer integration.
- No generated image or audio model; the UI renders uploaded media and Gemma's text answer.
- No tool execution or autonomous host access.
- No persistence guarantee; refreshing or rebooting clears the conversation.

## Trust boundaries

Port 8080 is the LAN boundary and is unauthenticated. Port 9379 is the model boundary and defaults to loopback. Input validation reduces accidental and obvious abuse but is not a substitute for authentication, TLS, rate limiting, or network isolation.

## Resource choices

The browser has no build tool or external runtime. The server dependencies are FastAPI, Uvicorn, HTTPX, and LiteRT-LM. This keeps the repository inspectable and avoids consuming Pi storage and memory on a front-end toolchain.
