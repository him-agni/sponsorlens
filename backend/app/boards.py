"""Job boards with public APIs that list a company's jobs: Greenhouse, Lever and Ashby.

A board is named by a key: "stripe" (Greenhouse, the original and the presets), "lever:palantir" or
"ashby:openai". The key is what batches store, and postings carry it in their source.
"""

import re
from urllib.parse import urlsplit

import httpx

from app import ashby, greenhouse, lever
from app.postings import Posting

_BY_NAME = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def _split(board: str) -> tuple[str, str]:
    name, _, token = board.rpartition(":")
    return (name or "greenhouse"), token


def key(name: str, token: str) -> str:
    return token if name == "greenhouse" else f"{name}:{token}"


def company(board: str) -> str:
    """The company part of a board key, for display: lever:palantir gives palantir."""
    return _split(board)[1]


async def fetch_board(client: httpx.AsyncClient, board: str) -> list[Posting]:
    name, token = _split(board)
    return await _BY_NAME[name].fetch_board(client, token)


def site_token(url: str) -> str | None:
    """The likely board name for a company's own careers site: www.databricks.com/careers gives databricks."""
    host = (urlsplit(url).hostname or "").lower()
    labels = [label for label in host.split(".") if label not in ("www", "careers", "jobs", "boards")]
    # Only a plain name goes into a board API path.
    if len(labels) < 2 or not re.fullmatch(r"[a-z0-9-]+", labels[-2]):
        return None
    return labels[-2]


async def find_board(client: httpx.AsyncClient, url: str) -> str | None:
    """The board key for a Greenhouse, Lever or Ashby board link, or for a company's careers site.

    For a careers site only the boards' own APIs are asked, never the site: Greenhouse first (it
    gives a company name to check), then Ashby, then Lever.
    """
    for name, module in _BY_NAME.items():
        if match := module.BOARD_URL.match(url):
            return key(name, match["token"].lower())
    token = site_token(url)
    if not token:
        return None
    for name in ("greenhouse", "ashby", "lever"):
        if await _BY_NAME[name].has_board(client, token):
            return key(name, token)
    return None
