from typing import Protocol

from openai import AsyncOpenAI

from app.config import settings


def make_client(max_retries: int = 2) -> AsyncOpenAI:
    """Token Factory is OpenAI-compatible, so the official SDK works with its base URL."""
    return AsyncOpenAI(base_url=settings.nebius_base_url, api_key=settings.nebius_api_key, max_retries=max_retries)


class ChatModel(Protocol):
    """The one call the analyzer needs, so tests and the engine can swap in a fake."""

    async def complete(self, model: str, messages: list[dict]) -> str: ...


class TokenFactoryModel:
    def __init__(self, client: AsyncOpenAI | None = None, max_tokens: int = 4096) -> None:
        # The engine's GuardedModel owns retries, so the SDK's own are off and every retry is counted.
        self.client = client or make_client(max_retries=0)
        self.max_tokens = max_tokens

    async def complete(self, model: str, messages: list[dict]) -> str:
        # Nemotron is not tagged for JSON mode in the catalog, but both models honored it in Phase 0.
        reply = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        return reply.choices[0].message.content or ""
