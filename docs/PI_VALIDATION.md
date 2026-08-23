# Raspberry Pi validation

This record separates captured terminal evidence, operator-reported browser evidence, and checks whose output was not captured.

## Target

- Raspberry Pi 5, 8 GB RAM, ARM64 Debian 13 (Trixie)
- 59 GB ext4 root filesystem on microSD with active cooling
- Python 3.13.5
- LiteRT-LM 0.16.1
- Gemma 4 E4B LiteRT model, imported as `gemma4-e4b`

## Validation record: 2026-08-23

The repository was cloned from merged `main` after PR #1 (`bb1ae07`). The installer reused the existing Hugging Face cache, imported the model into LiteRT-LM's registry, installed all application dependencies, and added the user command without source edits.

Captured `gemma-pi doctor` evidence:

| Check | Result |
| --- | --- |
| Architecture | `aarch64` — pass |
| Memory | 8063 MiB total, 7650 MiB available — pass |
| Disk | 34 GiB free — pass |
| Python | 3.13.5 — pass |
| LiteRT-LM | 0.16.1 — pass |
| Model | `gemma4-e4b` imported — pass |
| Temperature | 51.0 C |
| Firmware throttle | `throttled=0x0` — pass |
| Doctor result | ready |

`gemma-pi start` completed and printed a ready LAN URL. The operator then reported that the browser interface worked, text responses streamed, and uploaded media was recognized by the model. Gemma returned text; it did not generate images or audio, which is the intended V0 boundary.

Earlier direct-model testing also exercised text, a synthetic PNG, and a synthetic WAV in one prompt. The image description and ascending pitch direction were correct, but Gemma counted 10 tones when the fixture contained 3. That result demonstrates useful multimodal interpretation, not measurement-grade audio analysis.

## Evidence not captured

- The exact output of `scripts/smoke-test.sh` was not pasted into the validation record.
- A post-inference memory and temperature snapshot was not captured for the repository run.
- A clean `gemma-pi stop` followed by stopped status was not captured.

These are evidence gaps, not known failures. They must not be silently promoted to passes.

## Repeatable validation procedure

```bash
cd ~
git clone https://github.com/jeremybboy/gemma-pi-local.git
cd gemma-pi-local
./install.sh
~/.local/bin/gemma-pi doctor
~/.local/bin/gemma-pi start
~/.local/bin/gemma-pi status
./scripts/smoke-test.sh
```

From a browser on the same trusted LAN, open the URL from `gemma-pi ui` and verify text, image plus text, WAV plus text, image plus WAV plus text, reset, and page-refresh behavior. Then capture health and stop cleanly:

```bash
vcgencmd measure_temp
vcgencmd get_throttled
free -h
~/.local/bin/gemma-pi logs
~/.local/bin/gemma-pi stop
~/.local/bin/gemma-pi status
```

Model-answer correctness must be recorded separately from installer, transport, UI, resource, and process-control success.
