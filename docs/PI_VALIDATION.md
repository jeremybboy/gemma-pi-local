# Raspberry Pi validation

This document separates completed model evidence from pending application evidence.

## Existing target evidence

The initial target is a Raspberry Pi 5 with 8 GB RAM, ARM64 Debian 13 (Trixie), a 59 GB ext4 root filesystem on microSD, and active cooling. Before repository installation it had about 45 GB free, temperature readings between 33.4 C and 38.4 C at idle, and a current firmware throttle value of `0x0`.

LiteRT-LM 0.16.1 and the 3.4 GiB Gemma 4 E4B LiteRT model were run from a separate experiment. Text inference worked. A single text, synthetic-image, and synthetic-WAV request also worked: the image description and ascending pitch direction were correct, but the model counted 10 tones instead of the 3 in the fixture. Peak observed temperature was 73.6 C, later 55.4 C, with no swap use and `throttled=0x0`.

This proves basic model inference on that Pi. It does not yet prove this repository's installer, process control, web UI, or shutdown path.

## First repository validation run

Run from the Pi over SSH after the feature PR is available:

```bash
cd ~
git clone --branch feature/v1-foundation https://github.com/jeremybboy/gemma-pi-local.git
cd gemma-pi-local
./install.sh
~/.local/bin/gemma-pi doctor
~/.local/bin/gemma-pi start
~/.local/bin/gemma-pi status
./scripts/smoke-test.sh
```

From a browser on the same LAN, open the URL from `gemma-pi ui` and verify:

1. Status changes to ready and displays temperature, memory, and disk.
2. A text-only prompt streams a response.
3. A PNG or JPEG plus text streams a grounded response and displays the preview.
4. A WAV plus text streams a grounded response and displays a playable audio control.
5. One message with image, WAV, and text streams a response that acknowledges both files.
6. Reset removes the visible conversation.
7. A page refresh starts an empty conversation.

Then capture health and stop cleanly:

```bash
vcgencmd measure_temp
vcgencmd get_throttled
free -h
~/.local/bin/gemma-pi logs
~/.local/bin/gemma-pi stop
~/.local/bin/gemma-pi status
```

## Pass criteria

- Installation and commands complete without manual source edits.
- The model server remains bound to loopback and the UI is reachable only as configured.
- All five browser checks complete without a process crash or swap exhaustion.
- `gemma-pi stop` terminates both services.
- Logs do not contain credentials or unexpected remote calls.
- Temperature and throttle observations are recorded, not generalized beyond the tested hardware.

Record failures verbatim and keep the PR in draft until material defects are fixed. Model answer correctness should be described separately from transport and UI success.
