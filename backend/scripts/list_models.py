"""List the Nemotron models on Token Factory. Run from backend/: uv run python -m scripts.list_models"""

import asyncio

from app.llm import make_client


async def main() -> None:
    models = await make_client().models.list()
    for model in sorted(models.data, key=lambda m: m.id):
        if "nemotron" in model.id.lower():
            print(model.id)


if __name__ == "__main__":
    asyncio.run(main())
