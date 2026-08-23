# Changelog

All notable project changes are recorded here.

## [0.1.0] - 2026-08-23

### Added

- One-command Raspberry Pi installation and process control.
- Local Gemma 4 E4B text, image, and WAV input through LiteRT-LM 0.16.1.
- Streaming trusted-LAN browser UI with image previews and audio playback.
- Pi health display, doctor, smoke test, security guidance, and automated CI.

### Validated

- Installation from merged `main` on the target Raspberry Pi 5 8 GB without source edits.
- ARM64 runtime, Python 3.13.5, imported model, available memory and disk, temperature, and firmware throttle checks.
- One-command startup and operator-reported browser text and multimodal-input interaction.

### Known boundaries

- Responses are text-only; V0 does not generate images or audio.
- Media interpretation can be wrong and is not measurement-grade.
- Authentication, TLS, persistence, microphone capture, Behringer recording, and generated media are outside V0.
- Exact smoke-test, clean-shutdown, and post-inference health output were not captured in the repository validation record.
