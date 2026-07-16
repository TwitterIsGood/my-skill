from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def discover_env_file(path: str | Path | None = None) -> Path | None:
    """Find configuration in the caller's local project, never in the skill bundle."""
    if path:
        candidate = Path(path).expanduser().resolve()
        return candidate if candidate.is_file() else None
    explicit = os.getenv("UI_REPLICA_ENV_FILE")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return candidate if candidate.is_file() else None
    cwd = Path.cwd().resolve()
    for name in (".env.local", ".env", ".ui-replica.env"):
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(path: str | Path | None = None) -> Path | None:
    """Load simple KEY=VALUE entries without overriding exported variables."""
    env_path = discover_env_file(path)
    if env_path is None:
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
    return env_path


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    image_model: str = "gpt-image-2"
    ui_model: str = "gpt-5.6-sol"
    reasoning_effort: str | None = "xhigh"
    proxy: str | None = None
    timeout: int = 180
    max_retries: int = 2

    @classmethod
    def from_env(cls, require_key: bool = True) -> "Settings":
        load_dotenv()
        key = os.getenv("UI_REPLICA_API_KEY", "")
        if require_key and not key:
            raise ValueError("UI_REPLICA_API_KEY is required in the local project environment or env file")
        base = os.getenv("UI_REPLICA_BASE_URL", "").rstrip("/")
        if not base:
            raise ValueError("UI_REPLICA_BASE_URL is required in the local project environment or env file")
        return cls(
            base_url=base,
            api_key=key,
            image_model=os.getenv("UI_REPLICA_IMAGE_MODEL", "gpt-image-2"),
            ui_model=os.getenv("UI_REPLICA_UI_MODEL", "gpt-5.6-sol"),
            reasoning_effort=os.getenv("UI_REPLICA_REASONING_EFFORT", "xhigh") or None,
            proxy=os.getenv("UI_REPLICA_PROXY") or None,
            timeout=int(os.getenv("UI_REPLICA_TIMEOUT", "180")),
            max_retries=int(os.getenv("UI_REPLICA_MAX_RETRIES", "2")),
        )
