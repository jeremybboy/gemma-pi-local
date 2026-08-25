# Experimental Apple-silicon macOS profile

This profile runs the same FastAPI UI, Gemma 4 E4B model, LiteRT-LM gateway, and SearXNG search path as the Raspberry Pi project. It is an extension of `gemma-pi-local`, not a separate implementation or a claim of general desktop support.

## Validated system

- MacBook Pro `Mac15,6`
- Apple M3 Pro, 11 CPU cores, ARM64
- 36 GB unified memory
- macOS 26.6.2
- Python 3.13.1
- LiteRT-LM 0.16.1 and imported `gemma4-e4b`
- Colima 0.10.3, Docker CLI 29.7.2, Docker Compose 5.5.0

The proof completed a local arithmetic turn and a current-information turn that caused Gemma to emit a structured `web_search` call. SearXNG returned sources, the final answer cited them, and the browser rendered source cards. The model process used about 5.8 GB resident memory during the observed run; this is one measurement, not a minimum-memory guarantee or benchmark.

On 2026-08-25, the v0.2.0 machine-readable verifier also completed against the real stack. `gemma-local verify --json --live` reported 13 passes, zero warnings, zero failures, and two expected skips for temperature and firmware-throttle telemetry. It confirmed the installed Python and LiteRT-LM 0.16.1 runtime, imported `gemma4-e4b`, application/model/search readiness, an image-plus-WAV text round trip, and an agentic search response with five source links and cited text. The multimodal result proves transport and inference completion, not semantic correctness.

## Install

```bash
brew install git python@3.13 colima docker docker-compose
git clone https://github.com/jeremybboy/gemma-pi-local.git
cd gemma-pi-local
./install-macos.sh
```

The installer creates `.venv`, installs the pinned runtime, imports the multi-gigabyte model when missing, connects Homebrew's Compose plugin to the Docker CLI when necessary, and creates both `~/.local/bin/gemma-local` and `~/.local/bin/gemma-pi`. It does not install system packages or request an administrator password.

## Daily use

```bash
~/.local/bin/gemma-local start
open http://127.0.0.1:8080
```

`start` automatically starts Colima if its Docker daemon is unavailable, waits for Docker to become ready, then starts SearXNG on `127.0.0.1:8888`, LiteRT-LM on `127.0.0.1:9379`, and the UI on `127.0.0.1:8080`. You do not need to start Docker separately.

```bash
~/.local/bin/gemma-local status
~/.local/bin/gemma-local logs --follow
~/.local/bin/gemma-local verify --json
~/.local/bin/gemma-local verify --json --live
~/.local/bin/gemma-local stop
```

Stopping Gemma leaves SearXNG and Colima running so the next launch is faster. Stop those separately only when desired:

```bash
./scripts/searxng.sh stop
colima stop
```

## Security and observability

The Mac UI is localhost-only by default because it has no authentication or TLS. LiteRT-LM and SearXNG also remain on loopback. Prompt and media inference stays on the Mac; a search query and the search engines' responses necessarily cross the network when Gemma requests `web_search`.

Standard macOS commands used here do not expose the same temperature and firmware-throttle signals as Raspberry Pi OS, so those fields display `Unavailable`. Memory availability is an approximation derived from `vm_stat`; total memory and uptime come from `sysctl`.

## Evidence limits

This profile is validated on one Apple-silicon Mac only. Intel macOS, Windows, Linux laptops, sleep/wake recovery, sustained-load thermals, and automatic launch at login are not yet validated. Gemma can still produce incorrect statements; the system prompt now gives it accurate local deployment identity, but that is behavioral guidance rather than a security boundary.
