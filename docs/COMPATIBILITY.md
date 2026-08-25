# Compatibility and evidence matrix

This matrix tells humans and automated agents what is validated, merely
implemented, or unsupported. A shared code path is not hardware evidence.

## Evidence labels

| Label | Meaning |
| --- | --- |
| Validated | Captured execution evidence exists on the named hardware. |
| Operator reported | A person observed the behavior, but the complete output is not preserved. |
| Implemented, unvalidated | The code path exists, but no target-hardware result is recorded. |
| Unsupported | The installer rejects the platform or the project makes no compatibility commitment. |

## Platform support

| Platform | Status | Evidence and boundary |
| --- | --- | --- |
| Raspberry Pi 5, 8 GB, ARM64 Debian 13 | Primary; validated | Installation, doctor, startup, local inference, multimodal input, structured tool calling, and SearXNG were exercised on one device. This is not a performance guarantee. |
| Apple M3 Pro, 36 GB, macOS 26.6.2 | Experimental; validated | Installation, localhost startup, text inference, structured search, cited answers, and browser source cards were exercised on one device. |
| Other Apple-silicon Macs | Experimental; unvalidated | The installer accepts ARM64 macOS, but no other chip, memory size, or macOS release has recorded evidence. |
| Other ARM64 Linux systems with at least 8 GB RAM | Implemented, unvalidated | The Linux installer may pass its generic guards, but lifecycle, telemetry, and performance are designed around the Pi target. |
| Raspberry Pi with less than 8 GB RAM | Unsupported in V0 | The installer rejects systems reporting less than 7,000,000 kB total memory. |
| Raspberry Pi 4 | Unsupported | No installation, thermal, or inference evidence is recorded. |
| Intel macOS, x86-64 Linux, Windows | Unsupported | There is no validated installer or runtime profile. |

## Capability support

| Capability | Raspberry Pi 5 | Apple-silicon macOS | Boundary |
| --- | --- | --- | --- |
| Text input and streamed text response | Validated | Validated | Model answers can still be wrong. |
| PNG, JPEG, or WebP input | Operator reported through the browser; direct model fixture validated | Transport validated by the live verifier | One inline image per message; Mac semantic interpretation was not scored. |
| WAV input | Operator reported through the browser; direct model fixture validated | Transport validated by the live verifier | One WAV per message; semantic audio accuracy is not measurement-grade. |
| Image plus WAV in one turn | Validated with a synthetic fixture | Transport validated by the live verifier | The response is text only; Mac semantic interpretation was not scored. |
| Model-initiated SearXNG search | Validated for a bounded search cycle | Validated for a bounded search cycle | Search queries and upstream results leave the device. |
| Browser source cards | Operator reported | Validated | Links are constructed by the gateway, not trusted model text. |
| One-command application startup | Validated | Validated | Docker runs SearXNG; macOS uses Colima. |
| Machine-readable verification | Implemented, unvalidated on target | Validated | The Mac run passed 13 checks with no failures; Pi output is still required. |
| Authentication, TLS, multi-user accounts | Unsupported | Unsupported | Do not expose the application to the public internet. |
| Persistent chat history | Unsupported | Unsupported | Refreshing or rebooting clears the conversation. |
| Generated image or audio output | Unsupported | Unsupported | Separate generation models would be required. |

## Updating this matrix

Every upgrade requires the hardware identity, operating system, model, runtime
version, command, exit status, and relevant resource snapshot. Do not use an
automated unit test as evidence for real model inference or hardware support.
