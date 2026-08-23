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
    static_dir: Path = PROJECT_ROOT / "static"


settings = Settings()
