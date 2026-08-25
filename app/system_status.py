"""Read portable, non-sensitive host health without third-party dependencies."""

from __future__ import annotations

import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import time
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


def _linux_memory() -> dict[str, int | None] | None:
    values: dict[str, int] = {}
    raw = _read_text("/proc/meminfo")
    if not raw:
        return None
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


def _macos_memory() -> dict[str, int | None] | None:
    total_raw = _run(["sysctl", "-n", "hw.memsize"])
    vm_raw = _run(["vm_stat"])
    total_bytes: int | None = int(total_raw) if total_raw and total_raw.isdigit() else None
    if total_bytes is None:
        try:
            total_bytes = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        except (OSError, TypeError, ValueError):
            total_bytes = None
    if total_bytes is None:
        return None

    available_bytes: int | None = None
    if vm_raw:
        page_match = re.search(r"page size of (\d+) bytes", vm_raw)
        page_size = int(page_match.group(1)) if page_match else 4096
        page_counts: dict[str, int] = {}
        for line in vm_raw.splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            digits = value.strip().rstrip(".")
            if digits.isdigit():
                page_counts[key] = int(digits)
        available_pages = sum(
            page_counts.get(key, 0)
            for key in (
                "Pages free",
                "Pages inactive",
                "Pages speculative",
                "Pages purgeable",
            )
        )
        available_bytes = available_pages * page_size

    swap_total: int | None = None
    swap_free: int | None = None
    swap_raw = _run(["sysctl", "-n", "vm.swapusage"])
    if swap_raw:
        total_match = re.search(r"total = ([\d.]+)M", swap_raw)
        free_match = re.search(r"free = ([\d.]+)M", swap_raw)
        if total_match:
            swap_total = int(float(total_match.group(1)) * 1024 * 1024)
        if free_match:
            swap_free = int(float(free_match.group(1)) * 1024 * 1024)

    return {
        "total_bytes": total_bytes,
        "available_bytes": available_bytes,
        "swap_total_bytes": swap_total,
        "swap_free_bytes": swap_free,
    }


def _memory() -> dict[str, int | None]:
    values = _linux_memory()
    if values is None and platform.system() == "Darwin":
        values = _macos_memory()
    return values or {
        "total_bytes": None,
        "available_bytes": None,
        "swap_total_bytes": None,
        "swap_free_bytes": None,
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


def _uptime_seconds() -> int | None:
    uptime_raw = _read_text("/proc/uptime")
    if uptime_raw:
        try:
            return int(float(uptime_raw.split()[0]))
        except (ValueError, IndexError):
            pass
    if platform.system() == "Darwin":
        boot_raw = _run(["sysctl", "-n", "kern.boottime"])
        if boot_raw:
            match = re.search(r"sec\s*=\s*(\d+)", boot_raw)
            if match:
                return max(0, int(time.time()) - int(match.group(1)))
    return None


def snapshot() -> dict[str, Any]:
    """Return a small, non-sensitive system health snapshot."""

    disk = shutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "temperature_c": _temperature_c(),
        "throttled": _throttled(),
        "memory": _memory(),
        "disk": {
            "total_bytes": disk.total,
            "free_bytes": disk.free,
        },
        "uptime_seconds": _uptime_seconds(),
    }
