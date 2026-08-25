# Gemma Pi Local

[![CI](https://github.com/jeremybboy/gemma-pi-local/actions/workflows/ci.yml/badge.svg)](https://github.com/jeremybboy/gemma-pi-local/actions/workflows/ci.yml)

Ask Gemma 4 with text, images, and WAV audio on a Raspberry Pi 5—or experimentally on Apple silicon—then receive text responses and model-initiated web search in a local browser UI.

> **V0 validated:** on 2026-08-23, the repository installed without source edits on the target 8 GB Pi, passed `gemma-pi doctor`, started from one command, served the LAN interface, and completed operator-reported text and multimodal browser interactions.

## What it does

- Runs [Gemma 4 E4B](https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm) locally through [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM).
- Accepts text plus an optional image and optional WAV file in one browser conversation.
- Returns Gemma's text answer and renders uploaded images and audio players in the chat; evidence-grounded search answers stream after the tool decision.
- Lets Gemma request one bounded public-web search through a loopback-only SearXNG service, then shows numbered source links.
- Shows model readiness, available host health, memory, and disk space.
- Keeps chat history only in the current browser tab; no database or cloud service is used.
- Starts the model server and web interface with one command.

V0 analyzes media but does not generate images or audio. Generated media would require separate local models and is future work, not a hidden or broken feature.

## Target

V0 remains deliberately narrow: Raspberry Pi 5, 8 GB RAM, ARM64 Linux, active cooling, and at least 8 GB of free storage. An experimental localhost-only macOS profile is validated on one Apple-silicon Mac; it broadens the same application without weakening or renaming the Pi target.

## Install on the Pi

Install system prerequisites first. Docker runs the local SearXNG service; reconnect after adding your user to its group:

```bash
sudo apt update
sudo apt install -y git python3-venv curl docker.io docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Then clone and install:

```bash
cd ~
git clone https://github.com/jeremybboy/gemma-pi-local.git
cd gemma-pi-local
./install.sh
```

The installer creates a local Python environment, installs LiteRT-LM 0.16.1, imports the 3.4 GiB Gemma 4 E4B model, and adds a `gemma-pi` command under `~/.local/bin`.

## Install on Apple silicon macOS (experimental)

Install the unprivileged prerequisites with Homebrew; Colima supplies the local container VM, so Docker Desktop is not required:

```bash
brew install git python@3.13 colima docker docker-compose
git clone https://github.com/jeremybboy/gemma-pi-local.git
cd gemma-pi-local
./install-macos.sh
```

Start the complete local stack and open its localhost-only UI:

```bash
~/.local/bin/gemma-local start
open http://127.0.0.1:8080
```

The start command brings up Colima when needed, starts loopback-only SearXNG, then starts LiteRT-LM and the web app. Stop the app with `gemma-local stop`; Colima and SearXNG remain available for the next launch. See [docs/MACOS.md](docs/MACOS.md) for the evidence boundary and troubleshooting.

## Run

```bash
~/.local/bin/gemma-pi start
```

Open the URL printed by the command from a device on the same trusted LAN. Stop it with:

```bash
~/.local/bin/gemma-pi stop
```

Useful commands:

| Command | Purpose |
| --- | --- |
| `gemma-pi start` | Start LiteRT-LM and the web app in the background |
| `gemma-pi stop` | Stop both processes |
| `gemma-pi status` | Check the process, model server, and Pi health |
| `gemma-pi logs --follow` | Follow startup and inference logs |
| `gemma-pi ui` | Print the browser URL |
| `gemma-pi doctor` | Check architecture, RAM, disk, runtime, model, and thermals |

If `~/.local/bin` is already on your `PATH`, omit the full path.

## Configuration

Defaults work for the target Pi. For changes, copy the example and edit it before starting:

```bash
cp .env.example .env
```

The web UI defaults to `0.0.0.0:8080` on Linux/Pi and `127.0.0.1:8080` on macOS. LiteRT-LM defaults to `127.0.0.1:9379`, and SearXNG defaults to `127.0.0.1:8888`; both must remain loopback-only unless you add a separate security layer.

## Security boundary

V0 has **no authentication or TLS**. The Pi profile is only for a private, trusted LAN; the Mac profile defaults to this computer only. Do not port-forward it, expose it to the public internet, or override the Mac bind address without adding a separate security layer. Uploaded media and prompts are sent only to local LiteRT-LM, but search queries leave the device through SearXNG and configured upstream search engines.

The gateway accepts inline PNG, JPEG, or WebP images and WAV audio. It rejects remote media URLs, unsupported message roles, oversized requests, multiple images or audio files in one message, arbitrary model identifiers, unknown tools, multiple tool calls, and non-loopback search services. Search queries leave the Pi through SearXNG and configured upstream search engines.

See [SECURITY.md](SECURITY.md) for reporting and deployment guidance.

## What has actually been validated

Direct model inference on the target Raspberry Pi succeeded with one prompt containing text, a synthetic PNG, and a synthetic WAV. Gemma correctly described the illustrated house and recognized that the tones ascended, but reported 10 tones when the fixture contained 3; multimodal understanding is useful but not measurement-grade. During that run, memory stayed within 8 GB with no swap use, temperature peaked at 73.6 C, later returned to 55.4 C, and firmware reported `throttled=0x0`.

The merged repository was then installed from `main` on that Pi. Captured terminal evidence confirms ARM64, 8 GB RAM, 34 GB free disk, Python 3.13.5, LiteRT-LM 0.16.1, imported `gemma4-e4b`, 51.0 C, `throttled=0x0`, a ready doctor result, and successful LAN startup. The operator reported that browser interaction and media understanding worked and that responses were text-only as designed.

The exact evidence boundary, remaining uncaptured checks, and repeatable procedure are in [docs/PI_VALIDATION.md](docs/PI_VALIDATION.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

On macOS, the same application completed text-only and live-search turns on an Apple M3 Pro with 36 GB RAM, macOS 26.6.2, Python 3.13.1, LiteRT-LM 0.16.1, and Colima. The current proof covers one Apple-silicon machine, not Intel Macs or every macOS release; see [docs/MACOS.md](docs/MACOS.md).

## Architecture

```text
Trusted-LAN browser
        |
        | HTTP :8080
        v
FastAPI gateway + static UI
        |                              |
        | HTTP :9379 (loopback)        | HTTP :8888 (loopback)
        v                              v
LiteRT-LM -> Gemma 4 E4B           SearXNG -> public search engines
```

The UI has no JavaScript build step or external CDN. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for request flow and design boundaries.

## Development

On a development machine:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-dev.txt
.venv-dev/bin/python -m pytest
python3 -m compileall -q app
bash -n install.sh install-macos.sh start.sh bin/gemma-pi scripts/doctor.sh scripts/smoke-test.sh
```

The automated tests mock LiteRT-LM; they do not prove inference performance or Raspberry Pi compatibility. Contributions should follow [CONTRIBUTING.md](CONTRIBUTING.md).

## Direction

V0 optimizes for a repeatable local multimodal experiment, not a benchmark suite or a polished appliance. Next candidates include Behringer recording, generated-media rendering, optional authentication, persistent opt-in chats, service installation, and broader hardware validation; see [docs/ROADMAP.md](docs/ROADMAP.md).

Model-initiated, no-fee web search now uses a loopback-only SearXNG service. The model can request one bounded search, while the gateway owns execution and source cards; implementation and evidence gates are tracked in [docs/AGENTIC_SEARCH.md](docs/AGENTIC_SEARCH.md).

Related work worth studying includes [Mote](https://github.com/mkturkcan/mote), which focuses on highly optimized Gemma text inference on Raspberry Pi 5. This repository's different focus is a small, auditable, LiteRT-LM multimodal browser experience with operational health checks and explicit validation boundaries.

## Model terms and license

The application code is licensed under Apache-2.0. Gemma 4 weights and model artifacts are separate and subject to the [Gemma 4 Apache-2.0 license](https://ai.google.dev/gemma/apache_2) and any notices in their source repository; this installer downloads rather than redistributes them.
