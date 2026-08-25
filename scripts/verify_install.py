#!/usr/bin/env python3
"""Emit human-readable or JSON evidence for a Gemma Pi Local installation."""

from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import wave
import zlib


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.system_status import snapshot  # noqa: E402
from app.version import __version__  # noqa: E402


MIN_MEMORY_BYTES = 7_000_000 * 1024
MIN_FREE_DISK_BYTES = 4 * 1024**3
CITATION_PATTERN = re.compile(r"\[\d+\]")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class Check:
    """One stable verification result for humans and automation."""

    id: str
    label: str
    status: str
    required: bool
    detail: str


def _check(
    check_id: str,
    label: str,
    status: str,
    detail: str,
    *,
    required: bool = True,
) -> Check:
    if status not in {"pass", "warn", "fail", "skip"}:
        raise ValueError(f"Unsupported check status: {status}")
    return Check(check_id, label, status, required, detail)


def _run(command: list[str], timeout: float = 15.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    output = (result.stdout or result.stderr).strip()
    return result.returncode, output


def _loopback_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError("verification URL must be loopback HTTP")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("verification URL must not contain credentials or query data")
    if parsed.path not in {"", "/"}:
        raise ValueError("verification URL must not contain an application path")
    return raw_url.rstrip("/")


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("response was not a JSON object")
    return payload


def _post_chat(base_url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(str(exc)) from exc

    answer_parts: list[str] = []
    search_event: dict[str, Any] | None = None
    done = False
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            continue
        if not data:
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid SSE JSON: {exc}") from exc
        if not isinstance(event, dict):
            continue
        if event.get("type") == "search":
            search_event = event
            continue
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0]
        delta = choice.get("delta") if isinstance(choice, dict) else None
        content = delta.get("content") if isinstance(delta, dict) else None
        if isinstance(content, str):
            answer_parts.append(content)
    return {
        "answer": "".join(answer_parts).strip(),
        "done": done,
        "search": search_event,
    }


def _png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x55\xaf\xf5")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def _wav_bytes() -> bytes:
    sample_rate = 16_000
    duration_seconds = 0.2
    frames = bytearray()
    for index in range(int(sample_rate * duration_seconds)):
        value = int(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(frames))
    return buffer.getvalue()


def _multimodal_payload(model: str) -> dict[str, Any]:
    image = base64.b64encode(_png_bytes()).decode("ascii")
    audio = base64.b64encode(_wav_bytes()).decode("ascii")
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image}"},
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {"format": "wav", "data": audio},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Use both attachments and reply briefly. Do not search the web. "
                            "This is a transport smoke test, not a precision test."
                        ),
                    },
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 128,
    }


def _search_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Search the web for the current Raspberry Pi OS release and cite sources.",
            }
        ],
        "temperature": 0.2,
        "max_tokens": 384,
    }


def _preflight(base_url: str, model: str, timeout: float) -> tuple[list[Check], dict[str, Any] | None]:
    checks: list[Check] = []
    host = snapshot()
    system = platform.system()
    machine = platform.machine()

    checks.append(
        _check(
            "platform.os",
            "Operating system",
            "pass" if system in {"Linux", "Darwin"} else "fail",
            system,
        )
    )
    checks.append(
        _check(
            "platform.architecture",
            "Architecture",
            "pass" if machine in {"aarch64", "arm64"} else "fail",
            machine,
        )
    )

    total_memory = host["memory"].get("total_bytes")
    if isinstance(total_memory, int):
        memory_status = "pass" if total_memory >= MIN_MEMORY_BYTES else "fail"
        memory_detail = f"{total_memory // 1024 // 1024} MiB total"
    else:
        memory_status = "fail"
        memory_detail = "unavailable"
    checks.append(_check("host.memory", "Memory", memory_status, memory_detail))

    free_disk = host["disk"].get("free_bytes")
    if isinstance(free_disk, int):
        disk_status = "pass" if free_disk >= MIN_FREE_DISK_BYTES else "fail"
        disk_detail = f"{free_disk // 1024**3} GiB free"
    else:
        disk_status = "fail"
        disk_detail = "unavailable"
    checks.append(_check("host.disk", "Disk", disk_status, disk_detail))

    venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    checks.append(
        _check(
            "runtime.python",
            "Python environment",
            "pass" if venv_python.is_file() and os.access(venv_python, os.X_OK) else "fail",
            str(venv_python) if venv_python.exists() else "missing; run the installer",
        )
    )

    litert = ROOT_DIR / ".venv" / "bin" / "litert-lm"
    litert_ready = litert.is_file() and os.access(litert, os.X_OK)
    if litert_ready:
        version_code, version_output = _run([str(litert), "--version"])
        litert_ready = version_code == 0
    else:
        version_output = "missing; run the installer"
    checks.append(
        _check(
            "runtime.litert_lm",
            "LiteRT-LM",
            "pass" if litert_ready else "fail",
            version_output,
        )
    )

    model_ready = False
    model_detail = "LiteRT-LM unavailable"
    if litert_ready:
        model_code, model_output = _run([str(litert), "list"])
        model_ready = model_code == 0 and any(
            line.split() and line.split()[0] == model for line in model_output.splitlines()
        )
        model_detail = f"{model} imported" if model_ready else f"{model} not imported"
    checks.append(
        _check(
            "runtime.model_imported",
            "Model registration",
            "pass" if model_ready else "fail",
            model_detail,
        )
    )

    search_configured = os.getenv("GEMMA_PI_SEARCH_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    docker = shutil.which("docker")
    if not search_configured:
        checks.append(
            _check(
                "search.container_tools",
                "Container tools",
                "skip",
                "web search disabled by configuration",
                required=False,
            )
        )
    elif docker:
        compose_code, compose_output = _run([docker, "compose", "version"])
        checks.append(
            _check(
                "search.container_tools",
                "Container tools",
                "pass" if compose_code == 0 else "fail",
                compose_output or "Docker Compose unavailable",
            )
        )
    else:
        checks.append(
            _check(
                "search.container_tools",
                "Container tools",
                "fail",
                "Docker CLI missing",
            )
        )

    status_payload: dict[str, Any] | None = None
    try:
        status_payload = _get_json(f"{base_url}/api/status", min(timeout, 15.0))
    except RuntimeError as exc:
        checks.append(_check("service.app", "Web application", "fail", f"unavailable: {exc}"))
        checks.append(_check("service.model", "Model API", "fail", "application status unavailable"))
        checks.append(
            _check(
                "service.search",
                "Search API",
                "fail" if search_configured else "skip",
                "application status unavailable" if search_configured else "web search disabled",
                required=search_configured,
            )
        )
    else:
        app_ok = status_payload.get("app") == "ok"
        checks.append(
            _check(
                "service.app",
                "Web application",
                "pass" if app_ok else "fail",
                f"{base_url}/api/status",
            )
        )
        litert_status = status_payload.get("litert")
        model_api_ok = isinstance(litert_status, dict) and litert_status.get("ok") is True
        checks.append(
            _check(
                "service.model",
                "Model API",
                "pass" if model_api_ok else "fail",
                "ready" if model_api_ok else str((litert_status or {}).get("error", "offline")),
            )
        )
        search_status = status_payload.get("search")
        search_enabled = isinstance(search_status, dict) and search_status.get("enabled") is True
        search_ok = search_enabled and search_status.get("ok") is True
        if not search_enabled:
            checks.append(
                _check(
                    "service.search",
                    "Search API",
                    "skip",
                    "disabled",
                    required=False,
                )
            )
        else:
            checks.append(
                _check(
                    "service.search",
                    "Search API",
                    "pass" if search_ok else "fail",
                    "ready" if search_ok else str(search_status.get("error", "offline")),
                )
            )

    temperature = host.get("temperature_c")
    checks.append(
        _check(
            "host.temperature",
            "Temperature telemetry",
            "pass" if isinstance(temperature, (int, float)) else "skip",
            f"{temperature} C" if isinstance(temperature, (int, float)) else "unavailable on this host",
            required=False,
        )
    )
    throttle = host.get("throttled")
    if not isinstance(throttle, dict) or throttle.get("active") is None:
        throttle_check = _check(
            "host.throttle",
            "Firmware throttle",
            "skip",
            "unavailable or not applicable",
            required=False,
        )
    elif throttle.get("active") is True:
        throttle_check = _check(
            "host.throttle",
            "Firmware throttle",
            "fail",
            f"active: {', '.join(throttle.get('active_flags', []))}",
        )
    elif throttle.get("historical") is True:
        throttle_check = _check(
            "host.throttle",
            "Firmware throttle",
            "warn",
            f"historical: {', '.join(throttle.get('historical_flags', []))}",
            required=False,
        )
    else:
        throttle_check = _check(
            "host.throttle",
            "Firmware throttle",
            "pass",
            str(throttle.get("raw") or "no active flags"),
        )
    checks.append(throttle_check)
    return checks, status_payload


def _live_checks(base_url: str, model: str, timeout: float) -> list[Check]:
    checks: list[Check] = []
    try:
        multimodal = _post_chat(base_url, _multimodal_payload(model), timeout)
        multimodal_ok = bool(multimodal["answer"]) and multimodal["done"] is True
        checks.append(
            _check(
                "live.multimodal_roundtrip",
                "Image and WAV round trip",
                "pass" if multimodal_ok else "fail",
                (
                    "gateway accepted both attachments and returned text; semantic correctness not measured"
                    if multimodal_ok
                    else "response contained no completed text stream"
                ),
            )
        )
    except RuntimeError as exc:
        checks.append(
            _check(
                "live.multimodal_roundtrip",
                "Image and WAV round trip",
                "fail",
                str(exc),
            )
        )

    try:
        search = _post_chat(base_url, _search_payload(model), timeout)
        search_event = search.get("search")
        sources = search_event.get("sources") if isinstance(search_event, dict) else None
        search_ok = (
            search.get("done") is True
            and bool(search.get("answer"))
            and isinstance(sources, list)
            and bool(sources)
            and CITATION_PATTERN.search(str(search.get("answer"))) is not None
        )
        checks.append(
            _check(
                "live.agentic_search",
                "Agentic search round trip",
                "pass" if search_ok else "fail",
                (
                    f"structured search returned {len(sources)} source(s) and cited text"
                    if search_ok
                    else "no complete search event, source list, cited answer, or stream terminator"
                ),
            )
        )
    except RuntimeError as exc:
        checks.append(
            _check(
                "live.agentic_search",
                "Agentic search round trip",
                "fail",
                str(exc),
            )
        )
    return checks


def _result(checks: list[Check]) -> str:
    if any(item.required and item.status == "fail" for item in checks):
        return "fail"
    if any(item.status == "warn" for item in checks):
        return "pass_with_warnings"
    return "pass"


def _payload(checks: list[Check], live: bool) -> dict[str, Any]:
    result = _result(checks)
    counts = {
        status: sum(item.status == status for item in checks)
        for status in ("pass", "warn", "fail", "skip")
    }
    return {
        "schema_version": 1,
        "project": "gemma-pi-local",
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "live" if live else "runtime",
        "result": result,
        "summary": counts,
        "checks": [asdict(item) for item in checks],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    parser.add_argument(
        "--live",
        action="store_true",
        help="run real image-plus-WAV and agentic-search turns",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GEMMA_PI_APP_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument("--model", default=os.getenv("GEMMA_PI_MODEL", "gemma4-e4b"))
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        args.base_url = _loopback_url(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks, status_payload = _preflight(args.base_url, args.model, args.timeout)
    if args.live:
        if status_payload is None:
            checks.extend(
                [
                    _check(
                        "live.multimodal_roundtrip",
                        "Image and WAV round trip",
                        "fail",
                        "application status unavailable",
                    ),
                    _check(
                        "live.agentic_search",
                        "Agentic search round trip",
                        "fail",
                        "application status unavailable",
                    ),
                ]
            )
        else:
            checks.extend(_live_checks(args.base_url, args.model, args.timeout))
    else:
        checks.extend(
            [
                _check(
                    "live.multimodal_roundtrip",
                    "Image and WAV round trip",
                    "skip",
                    "run with --live",
                    required=False,
                ),
                _check(
                    "live.agentic_search",
                    "Agentic search round trip",
                    "skip",
                    "run with --live",
                    required=False,
                ),
            ]
        )

    report = _payload(checks, args.live)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Gemma Pi Local verifier {report['version']}")
        print(f"Mode: {report['mode']}")
        print()
        for item in checks:
            print(f"[{item.status.upper():4}] {item.label}: {item.detail}")
        print()
        print(f"Verifier result: {report['result']}")
    return 1 if report["result"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
