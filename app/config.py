"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    value = _positive_int(name, default)
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    """Configuration for the web gateway and LiteRT-LM server."""

    litert_base_url: str = os.getenv(
        "GEMMA_PI_LITERT_URL", "http://127.0.0.1:9379/v1"
    ).rstrip("/")
    default_model: str = os.getenv("GEMMA_PI_MODEL", "gemma4-e4b")
    max_request_bytes: int = _positive_int(
        "GEMMA_PI_MAX_REQUEST_BYTES", 32 * 1024 * 1024
    )
    max_attachment_bytes: int = _positive_int(
        "GEMMA_PI_MAX_ATTACHMENT_BYTES", 8 * 1024 * 1024
    )
    max_messages: int = _positive_int("GEMMA_PI_MAX_MESSAGES", 24)
    search_enabled: bool = _boolean("GEMMA_PI_SEARCH_ENABLED", False)
    searxng_base_url: str = os.getenv(
        "GEMMA_PI_SEARXNG_URL", "http://127.0.0.1:8888"
    ).rstrip("/")
    search_timeout_seconds: float = _positive_float(
        "GEMMA_PI_SEARCH_TIMEOUT_SECONDS", 12.0
    )
    search_max_results: int = _bounded_int(
        "GEMMA_PI_SEARCH_MAX_RESULTS", 5, minimum=1, maximum=10
    )
    static_dir: Path = PROJECT_ROOT / "static"


settings = Settings()
