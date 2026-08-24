# Contributing

Gemma Pi Local is an experiment with a narrow, evidence-first V0. Changes should keep setup understandable to someone operating a headless Raspberry Pi over SSH.

## Workflow

1. Open an issue for behavior changes or hardware support.
2. Create a focused branch from `main`.
3. Add or update tests and documentation with the code.
4. Run the local checks below.
5. Open a draft pull request and state which claims were tested on real hardware.

```bash
python3 -m compileall -q app
python3 -m pytest
bash -n install.sh start.sh bin/gemma-pi scripts/doctor.sh scripts/smoke-test.sh scripts/searxng.sh scripts/pi-search-gate.sh
node --check static/app.js
```

Do not describe mocked tests as Raspberry Pi validation. Hardware reports should include Pi model, RAM, OS, architecture, storage, LiteRT-LM/model versions, peak temperature, throttle state, result, and relevant logs with secrets removed.

## Scope rules

- Keep LiteRT-LM on loopback by default.
- Do not add telemetry, cloud calls, remote assets, or persistence without explicit documentation and opt-in behavior.
- Do not commit model weights, generated caches, `.env`, logs, credentials, or private network details.
- Prefer standard-library or small dependencies because memory and storage are constrained.

By contributing, you agree that your contribution is licensed under Apache-2.0.
