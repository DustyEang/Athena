"""Environment configuration. All secrets come from env / .env — never code."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = three levels up from this file (services/api/athena_api/config.py)
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Process-level settings (env). User-editable settings live in the DB
    (see routers/settings.py) so the UI can change them without restarts."""

    model_config = SettingsConfigDict(
        env_prefix="ATHENA_",
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"  # local | server | hybrid
    api_port: int = 8765
    data_dir: Path | None = None

    # Providers
    ollama_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.1"
    embed_model: str = "nomic-embed-text"
    fable5_api_key: str = ""
    fable5_model: str = "claude-fable-5"
    fable5_api_url: str = "https://api.anthropic.com/v1/messages"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    openai_api_url: str = "https://api.openai.com/v1/chat/completions"
    openai_extra_models: list[str] = ["gpt-5.5", "gpt-5.4-nano", "gpt-4o-mini"]

    # Future remote Athena server (stub in v1)
    server_url: str = ""
    server_token: str = ""

    voice_enabled: bool = False

    @property
    def resolved_data_dir(self) -> Path:
        d = self.data_dir or (REPO_ROOT / "data")
        d.mkdir(parents=True, exist_ok=True)
        (d / "logs").mkdir(exist_ok=True)
        return d

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "athena.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
