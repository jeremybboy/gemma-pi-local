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
