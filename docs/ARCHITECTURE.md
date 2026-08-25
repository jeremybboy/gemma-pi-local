# Architecture

## Components

1. `static/` is an offline browser client built with plain HTML, CSS, and JavaScript. It holds the current tab's conversation and media previews in memory.
2. `app/` is a small FastAPI gateway. It serves the UI, validates requests, reports non-sensitive host health, controls the single allowed web-search tool, and streams LiteRT-LM responses.
3. LiteRT-LM serves its OpenAI-compatible API on loopback and owns model loading and inference.
4. SearXNG serves its JSON Search API on loopback port 8888. It is the only component that queries external search engines.
5. `bin/gemma-pi` (also installed as `gemma-local` on macOS) starts SearXNG when available, controls the model/UI processes, and exposes status, logs, URL, and doctor commands.

## Multimodal request flow

The browser reads selected files locally, checks type and size, and converts them to base64. A user message is sent as OpenAI-compatible content parts in this order: image, audio, then text. The gateway validates the same constraints again and forwards the request to `/v1/chat/completions` with streaming enabled.

With search disabled, LiteRT-LM emits server-sent events that the gateway relays. With agentic search enabled, the gateway first requests a non-streamed response that is either direct text or a structured tool call. Direct text is emitted as one browser event after inference; a valid `web_search(query)` call triggers one bounded SearXNG request followed by one streamed Gemma answer using the normalized snippets as untrusted evidence. The browser renders the query and deterministic source links from a gateway-owned event rather than trusting model-generated links.

## Deliberate V0 boundaries

- One process group, one user, one active browser conversation.
- No accounts, database, cookies, analytics, telemetry, or cloud inference.
- No microphone capture or direct Behringer integration.
- No generated image or audio model; the UI renders uploaded media and Gemma's text answer.
- One fixed `web_search(query)` tool; no shell, filesystem, arbitrary URL fetch, browser action, or autonomous host access.
- No persistence guarantee; refreshing or rebooting clears the conversation.

## Trust boundaries

On the Pi, port 8080 is the unauthenticated trusted-LAN boundary. On macOS it binds to loopback by default, making the browser on that Mac the boundary. Ports 9379 and 8888 are the model and search boundaries and remain loopback-only. Search titles and snippets are untrusted external input. Input validation reduces accidental and obvious abuse but is not a substitute for authentication, TLS, rate limiting, or network isolation.

## Resource choices

The browser has no build tool or external runtime. The server dependencies are FastAPI, Uvicorn, HTTPX, and LiteRT-LM. This keeps the repository inspectable and avoids consuming Pi storage and memory on a front-end toolchain.
