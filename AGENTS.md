# Agent operating guide

This repository is an executable reference implementation for running Gemma 4
locally on constrained hardware. Treat the repository files and captured
validation records as the source of truth; do not promote an expected or
operator-reported behavior to a verified capability.

## Mission

Preserve a small, inspectable stack that another developer or coding agent can
install, verify, and extend without rediscovering the deployment architecture.
The primary target is a Raspberry Pi 5 with 8 GB RAM. Apple-silicon macOS is an
experimental second profile that runs the same application.

## Ground truth

- `README.md` is the human entry point and concise product contract.
- `docs/COMPATIBILITY.md` is the platform and capability evidence matrix.
- `docs/PI_VALIDATION.md` and `docs/MACOS.md` contain device-specific evidence.
- `docs/ARCHITECTURE.md` defines component and trust boundaries.
- `SECURITY.md` defines acceptable exposure.
- `VERSION` is the release version consumed by the application and tag checks.

When these documents disagree, use the narrowest claim supported by captured
evidence and update the stale document in the same pull request.

## Canonical commands

Raspberry Pi installation and operation:

```bash
./install.sh
~/.local/bin/gemma-pi doctor
~/.local/bin/gemma-pi start
~/.local/bin/gemma-pi verify --json
~/.local/bin/gemma-pi verify --json --live
```

Apple-silicon macOS installation and operation:

```bash
./install-macos.sh
~/.local/bin/gemma-local doctor
~/.local/bin/gemma-local start
~/.local/bin/gemma-local verify --json
~/.local/bin/gemma-local verify --json --live
```

`verify --json` checks the installed runtime, model registration, running APIs,
search service, host resources, and available thermal signals. `--live` adds a
real image-plus-WAV round trip and a model-initiated search turn. A successful
transport check does not prove that the model interpreted media correctly.

## Architecture and extension points

- `bin/gemma-pi`: lifecycle and operator command surface for both profiles.
- `start.sh`: LiteRT-LM and FastAPI process startup.
- `app/main.py`: request validation, API status, chat streaming, and the bounded
  tool loop.
- `app/agent.py`: system instructions and structured tool-call contract.
- `app/search/searxng.py`: constrained SearXNG adapter and evidence rendering.
- `app/system_status.py`: portable, non-sensitive host telemetry.
- `static/`: dependency-free browser interface.
- `scripts/verify_install.py`: machine-readable installation and live checks.
- `tests/`: mocked protocol and validation tests; these do not replace hardware
  validation.

Add a capability at the narrowest owning layer. Keep hardware-specific logic
out of the browser, and keep model-generated content out of tool authorization
and source-link construction.

## Invariants

- LiteRT-LM and SearXNG remain loopback-only.
- The Pi UI is unauthenticated trusted-LAN HTTP; the Mac UI defaults to
  localhost. Never describe either as safe for public exposure.
- Only a validated structured `web_search(query)` call may trigger networking.
- One user turn may execute at most one bounded search.
- Search titles and snippets are untrusted input, not instructions.
- Remote media URLs, arbitrary model identifiers, unknown tools, and multiple
  image or audio attachments remain rejected.
- Gemma returns text only. Uploaded images and WAV files are inputs; this
  project does not generate image or audio media.
- Chat persistence, authentication, TLS, arbitrary URL fetching, shell access,
  and filesystem tools are outside the current product boundary.

## Change discipline

Before opening a pull request, run:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-dev.txt
.venv-dev/bin/python -m pytest
.venv-dev/bin/python -m compileall -q app scripts
bash -n install.sh install-macos.sh start.sh bin/gemma-pi scripts/*.sh
node --check static/app.js
```

For runtime changes, also run `verify --json --live` on each platform whose
support claim changes and preserve sanitized output in the relevant validation
document. Record semantic answer quality separately from installation,
transport, process, resource, and tool-protocol success.

Use a feature branch and pull request. Do not publish a tag until the release
commit is on `main`; pushing a matching `v*` tag invokes the release workflow.
