from pathlib import Path
from typing import Literal

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
    # USD per million tokens (input, output), from the same catalog. Reasoning tokens bill as output.
    model_prices: dict[str, tuple[float, float]] = {
        "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
        "nvidia/Nemotron-3-Ultra-550b-a55b": (1.0, 3.0),
    }

    # "fake" runs the engine on FakeModel: no key, no cost, and /api/rehearsal is enabled.
    model_backend: Literal["live", "fake"] = "live"
    shards: int = 4
    # Totals across all shards.
    workers: int = 8
    queue_capacity: int = 32
    # Measured limits on Oct 24: Nano 100 RPM, Ultra 300 RPM and 200K TPM. Eight calls at a few
    # seconds each stays well under both.
    model_concurrency: int = 8
    fake_latency: float = 0.4
    # The append-only log, replayed on startup. On Render's free tier it is wiped when the service sleeps.
    log_path: Path = REPO_ROOT / "backend" / "data" / "sponsorlens.jsonl"

    # Limits for the public demo. The budget is per UTC day and kept in memory, so a restart resets it;
    # the hourly limit on the public endpoints bounds how fast it can be spent between restarts.
    daily_budget_usd: float = 1.0
    hourly_requests: int = 60
    # Render sets this to false, so batches there show the recorded run instead of spending credits.
    live_batches: bool = True

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
