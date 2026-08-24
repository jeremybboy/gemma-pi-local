# Agentic web-search experiment

This document is the restart point for adding no-fee, model-initiated web search to Gemma Pi Local. It records what is implemented, what still requires evidence from the target Raspberry Pi, and the exact boundary of the experiment.

## Target behavior

```text
Browser message
    |
    v
Gemma pass 1 -- decides locally whether web_search(query) is needed
    | no                                  | yes (at most once)
    v                                     v
Return local answer                 SearXNG on 127.0.0.1:8888
                                          |
                                          v
                                  bounded result snippets
                                          |
                                          v
                                  Gemma pass 2 + citations
                                          |
                                          v
                                  streamed answer + source links
```

There is no manual search toggle in the intended interface. The model receives one declared function, `web_search(query)`, and the gateway—not the model—owns execution, limits, timeouts, and source formatting.

## Current checkpoint

Implemented on `feature/agentic-web-search`:

- A loopback-only SearXNG Compose service on port 8888 with JSON output enabled.
- A constrained Python adapter with a 300-character query cap, fixed loopback service URL, timeout, maximum result count, URL validation, deduplication, and deterministic source numbers.
- A real-runtime probe that checks whether LiteRT-LM 0.16.1 returns OpenAI-compatible structured `tool_calls` for Gemma 4 E4B.
- A guarded `/api/chat` loop: one non-streamed model decision, at most one search, then one streamed evidence-grounded answer.
- Browser searching state, deterministic source links, and separate current-versus-historical throttle display.
- `gemma-pi start` attempts to ensure SearXNG is running; `gemma-pi stop` leaves the lightweight search service available.
- Local automated tests for the adapter, tool protocol, gateway, and existing V0 behavior.

Not validated yet:

- The complete two-pass `/api/chat` path on the target Pi.
- Browser rendering of live source cards on the target Pi.
- Repeated thermal, memory, and shutdown behavior under full search-answer cycles.

Treating text that merely resembles a function call as authorization to access the web remains forbidden. Only the validated structured call is executable.

## Gate 1 result: passed on the target Pi

On 2026-08-24, the target Raspberry Pi returned a structured `web_search` call for `current Raspberry Pi OS release`, SearXNG returned live results, and its log showed one Granian worker. The snapshot reported 2.6 GiB used, 5.2 GiB available, no swap use, and 61.5 C.

`throttled=0xe0000` had no active low-bit condition, but it records historical Arm frequency capping, throttling, and a soft-temperature-limit event. This is not a clean thermal-history result. Docker reported `0B / 0B` for container memory, so SearXNG-specific memory remains unmeasured; system-wide memory is the usable evidence.

## Why SearXNG runs on the Pi

The target is a self-contained local appliance, and SearXNG itself does not load another AI model. It sends ordinary search requests to configured engines and normalizes their result pages. The deployment omits Valkey because the service is single-user, bound to loopback, and has SearXNG's public-instance limiter disabled.

The official SearXNG documentation advises keeping Granian's worker defaults. We therefore do not force a worker count; target validation must record the observed worker count and actual memory use rather than assume either.

## Security boundary

- SearXNG is published only as `127.0.0.1:8888`; it is not reachable from the LAN.
- The Gemma Pi browser app remains unauthenticated HTTP on the trusted LAN. Anyone who can reach port 8080 can still cause local inference and, after integration, outgoing searches.
- Search snippets and titles are untrusted external text. The gateway labels them as evidence, never as system instructions.
- V1 permits one search call per user turn and at most ten normalized results; the planned default is five.
- This slice does not fetch arbitrary result pages, execute browser actions, submit forms, or download files.

## Real-Pi gate 1: runtime and tool-call probe

From the repository on the Raspberry Pi, first check whether Docker is already available:

```bash
cd /home/uzan/gemma4-lab/gemma-pi-local
docker --version
docker compose version
```

On Debian 13, the distribution packages are `docker.io` and `docker-compose`. If the checks fail:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker "$USER"
```

Reconnect the SSH session so the new `docker` group applies, then run the complete first gate:

```bash
cd /home/uzan/gemma4-lab/gemma-pi-local
./scripts/pi-search-gate.sh
```

The gate script starts SearXNG, executes a live search, starts Gemma Pi Local if needed, checks for a structured tool call, and prints one resource snapshot. To run only the model tool-call check against an already-running LiteRT-LM server, execute:

```bash
cd /home/uzan/gemma4-lab/gemma-pi-local
.venv/bin/python scripts/probe-tool-call.py
```

The gate passes only if the script prints `PASS` and a structured `web_search` call containing a string `query`. A prose answer, a code block, or JSON embedded only in `content` does not pass.

## Real-Pi gate 2: integrated chat and resource capture

After pulling the latest feature branch, restart Gemma Pi Local so the new gateway code is loaded, then run one local turn and one complete search-answer turn:

```bash
cd /home/uzan/gemma4-lab/gemma-pi-local
~/.local/bin/gemma-pi stop
~/.local/bin/gemma-pi start
.venv/bin/python scripts/probe-agent-search.py --cycles 1
```

Then capture:

```bash
docker stats --no-stream gemma-pi-searxng
free -h
vcgencmd measure_temp
vcgencmd get_throttled
```

Final chat validation will require two current-information prompts, two local-only prompts, three consecutive search cycles, correct clickable source links, and no shutdown, OOM, thermal throttling, or firmware undervoltage event.

## Primary references

- [SearXNG container installation](https://docs.searxng.org/admin/installation-docker.html)
- [SearXNG Search API](https://docs.searxng.org/dev/search_api.html)
- [SearXNG search settings](https://docs.searxng.org/admin/settings/settings_search.html)
- [SearXNG server settings](https://docs.searxng.org/admin/settings/settings_server.html)
- [SearXNG Granian guidance](https://docs.searxng.org/admin/installation-granian.html)
- [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/)
