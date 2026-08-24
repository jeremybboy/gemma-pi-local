"""Read Raspberry Pi health information without third-party dependencies."""

from __future__ import annotations

from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any


THROTTLE_FLAGS = (
    (0, "undervoltage"),
    (1, "arm_frequency_capped"),
    (2, "throttled"),
    (3, "soft_temperature_limit"),
)


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def _run(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _memory() -> dict[str, int | None]:
    values: dict[str, int] = {}
    raw = _read_text("/proc/meminfo")
    if raw:
        for line in raw.splitlines():
            key, _, value = line.partition(":")
            fields = value.strip().split()
            if fields and fields[0].isdigit():
                values[key] = int(fields[0]) * 1024
    return {
        "total_bytes": values.get("MemTotal"),
        "available_bytes": values.get("MemAvailable"),
        "swap_total_bytes": values.get("SwapTotal"),
        "swap_free_bytes": values.get("SwapFree"),
    }


def _temperature_c() -> float | None:
    raw = _read_text("/sys/class/thermal/thermal_zone0/temp")
    if raw:
        try:
            return round(float(raw) / 1000.0, 1)
        except ValueError:
            pass
    raw = _run(["vcgencmd", "measure_temp"])
    if raw and "=" in raw:
        try:
            return round(float(raw.split("=", 1)[1].split("'", 1)[0]), 1)
        except ValueError:
            pass
    return None


def _throttled() -> dict[str, Any]:
    raw = _run(["vcgencmd", "get_throttled"])
    if not raw or "=" not in raw:
        return {
            "raw": None,
            "active": None,
            "historical": None,
            "active_flags": [],
            "historical_flags": [],
            "active_or_historical": None,
        }
    value = raw.split("=", 1)[1].strip()
    try:
        numeric = int(value, 16)
    except ValueError:
        return {
            "raw": value,
            "active": None,
            "historical": None,
            "active_flags": [],
            "historical_flags": [],
            "active_or_historical": None,
        }
    active_flags = [name for bit, name in THROTTLE_FLAGS if numeric & (1 << bit)]
    historical_flags = [
        name for bit, name in THROTTLE_FLAGS if numeric & (1 << (bit + 16))
    ]
    return {
        "raw": value,
        "active": bool(active_flags),
        "historical": bool(historical_flags),
        "active_flags": active_flags,
        "historical_flags": historical_flags,
        "active_or_historical": bool(active_flags or historical_flags),
    }


def snapshot() -> dict[str, Any]:
    """Return a small, non-sensitive system health snapshot."""

    disk = shutil.disk_usage("/")
    uptime_raw = _read_text("/proc/uptime")
    uptime_seconds: int | None = None
    if uptime_raw:
        try:
            uptime_seconds = int(float(uptime_raw.split()[0]))
        except (ValueError, IndexError):
            pass
    return {
        "hostname": socket.gethostname(),
        "temperature_c": _temperature_c(),
        "throttled": _throttled(),
        "memory": _memory(),
        "disk": {
            "total_bytes": disk.total,
            "free_bytes": disk.free,
        },
        "uptime_seconds": uptime_seconds,
    }
