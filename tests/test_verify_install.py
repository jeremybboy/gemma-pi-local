import json
from pathlib import Path

import pytest

from app.version import __version__
from scripts import verify_install


def test_version_matches_canonical_file() -> None:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    assert __version__ == version_file.read_text(encoding="utf-8").strip()
    assert (version_file.parent / "docs" / "releases" / f"v{__version__}.md").is_file()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8080",
        "http://localhost:8080/",
        "http://[::1]:8080",
    ],
)
def test_loopback_url_accepts_only_local_http(url: str) -> None:
    assert verify_install._loopback_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8080",
        "http://192.168.1.10:8080",
        "http://example.com",
        "http://user:pass@localhost:8080",
        "http://localhost:8080/unexpected-path",
    ],
)
def test_loopback_url_rejects_nonlocal_or_credentialed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        verify_install._loopback_url(url)


def test_generated_multimodal_fixtures_have_real_container_headers() -> None:
    assert verify_install._png_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    wav = verify_install._wav_bytes()
    assert wav.startswith(b"RIFF")
    assert wav[8:12] == b"WAVE"


def test_required_failure_controls_overall_result() -> None:
    checks = [
        verify_install._check("a", "A", "pass", "ok"),
        verify_install._check("b", "B", "fail", "optional", required=False),
    ]
    assert verify_install._result(checks) == "pass"
    checks.append(verify_install._check("c", "C", "fail", "required"))
    assert verify_install._result(checks) == "fail"


def test_main_emits_stable_json_without_live_calls(monkeypatch, capsys) -> None:
    checks = [verify_install._check("service.app", "App", "pass", "ready")]
    monkeypatch.setattr(
        verify_install,
        "_preflight",
        lambda _base_url, _model, _timeout: (checks, {"app": "ok"}),
    )

    assert verify_install.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["version"] == __version__
    assert payload["mode"] == "runtime"
    assert payload["result"] == "pass"
    assert {item["id"] for item in payload["checks"]} == {
        "service.app",
        "live.multimodal_roundtrip",
        "live.agentic_search",
    }
