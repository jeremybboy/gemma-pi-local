from app import system_status
from app.system_status import snapshot


def test_snapshot_has_stable_public_shape() -> None:
    result = snapshot()
    assert set(result) == {
        "hostname",
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
