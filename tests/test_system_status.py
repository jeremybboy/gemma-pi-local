from app import system_status
from app.system_status import snapshot


def test_snapshot_has_stable_public_shape() -> None:
    result = snapshot()
    assert set(result) == {
        "hostname",
        "platform",
        "temperature_c",
        "throttled",
        "memory",
        "disk",
        "uptime_seconds",
    }
    assert set(result["memory"]) == {
        "total_bytes",
        "available_bytes",
        "swap_total_bytes",
        "swap_free_bytes",
    }
    assert set(result["disk"]) == {"total_bytes", "free_bytes"}


def test_macos_memory_uses_sysctl_and_vm_stat(monkeypatch) -> None:
    monkeypatch.setattr(system_status, "_read_text", lambda _path: None)
    monkeypatch.setattr(system_status.platform, "system", lambda: "Darwin")

    def fake_run(command: list[str]) -> str | None:
        if command == ["sysctl", "-n", "hw.memsize"]:
            return "38654705664"
        if command == ["vm_stat"]:
            return """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free: 100.
Pages inactive: 200.
Pages speculative: 50.
Pages purgeable: 25.
"""
        if command == ["sysctl", "-n", "vm.swapusage"]:
            return "total = 1024.00M  used = 256.00M  free = 768.00M"
        return None

    monkeypatch.setattr(system_status, "_run", fake_run)
    result = system_status._memory()
    assert result == {
        "total_bytes": 38654705664,
        "available_bytes": 375 * 16384,
        "swap_total_bytes": 1024 * 1024 * 1024,
        "swap_free_bytes": 768 * 1024 * 1024,
    }


def test_macos_uptime_uses_boot_time(monkeypatch) -> None:
    monkeypatch.setattr(system_status, "_read_text", lambda _path: None)
    monkeypatch.setattr(system_status.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        system_status,
        "_run",
        lambda command: "{ sec = 1000, usec = 0 }" if command[-1] == "kern.boottime" else None,
    )
    monkeypatch.setattr(system_status.time, "time", lambda: 1600)
    assert system_status._uptime_seconds() == 600


def test_macos_memory_falls_back_to_sysconf(monkeypatch) -> None:
    monkeypatch.setattr(system_status, "_run", lambda _command: None)

    def fake_sysconf(name: str) -> int:
        return {"SC_PHYS_PAGES": 100, "SC_PAGE_SIZE": 16_384}[name]

    monkeypatch.setattr(system_status.os, "sysconf", fake_sysconf)
    result = system_status._macos_memory()
    assert result == {
        "total_bytes": 100 * 16_384,
        "available_bytes": None,
        "swap_total_bytes": None,
        "swap_free_bytes": None,
    }


def test_throttle_status_separates_current_and_historical(monkeypatch) -> None:
    monkeypatch.setattr(
        system_status,
        "_run",
        lambda _command: "throttled=0xe0000",
    )
    result = system_status._throttled()
    assert result["active"] is False
    assert result["historical"] is True
    assert result["active_flags"] == []
    assert result["historical_flags"] == [
        "arm_frequency_capped",
        "throttled",
        "soft_temperature_limit",
    ]
