from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Read from environment variables, falling back to the repo-root .env file. Blank values keep the defaults."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore", env_ignore_empty=True)

    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    # IDs from the public Token Factory catalog (tokenfactory.nebius.com/api/public/models_info), Oct 23, 2026.
    nano_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    ultra_model: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    tavily_api_key: str = ""


settings = Settings()
