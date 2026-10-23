from openai import AsyncOpenAI

from app.config import settings


def make_client() -> AsyncOpenAI:
    """Token Factory is OpenAI-compatible, so the official SDK works with its base URL."""
    return AsyncOpenAI(base_url=settings.nebius_base_url, api_key=settings.nebius_api_key)
