import httpx
import pytest

from app import boards


def api(greenhouse: dict[str, str] | None = None, ashby: frozenset[str] = frozenset(), lever: frozenset[str] = frozenset()):
    """A client whose board APIs know only the given companies, recording which hosts were asked."""
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.host)
        token = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        if request.url.host == "boards-api.greenhouse.io" and token in (greenhouse or {}):
            return httpx.Response(200, json={"name": greenhouse[token]})
        if request.url.host == "api.ashbyhq.com" and token in ashby:
            return httpx.Response(200, json={"jobs": []})
        if request.url.host == "api.lever.co" and token in lever:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), asked


@pytest.mark.parametrize(
    ("url", "board"),
    [
        ("https://job-boards.greenhouse.io/Stripe/jobs/1", "stripe"),
        ("https://jobs.lever.co/palantir", "lever:palantir"),
        ("https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd", "lever:palantir"),
        ("https://jobs.ashbyhq.com/openai/240d459b", "ashby:openai"),
    ],
)
async def test_a_board_link_names_its_board_without_asking_anyone(url, board) -> None:
    client, asked = api()
    async with client:
        assert await boards.find_board(client, url) == board
    assert asked == []


async def test_a_careers_site_tries_greenhouse_then_ashby_then_lever() -> None:
    client, asked = api(greenhouse={"databricks": "Databricks"}, ashby=frozenset({"openai"}), lever=frozenset({"palantir"}))
    async with client:
        assert await boards.find_board(client, "https://www.databricks.com/careers") == "databricks"
        assert await boards.find_board(client, "https://openai.com/careers/search") == "ashby:openai"
        assert await boards.find_board(client, "https://www.palantir.com/careers/") == "lever:palantir"
        assert await boards.find_board(client, "https://www.notion.so/careers") is None
    assert asked[-3:] == ["boards-api.greenhouse.io", "api.ashbyhq.com", "api.lever.co"]


def test_a_careers_site_gives_its_likely_board_name() -> None:
    assert boards.site_token("https://www.databricks.com/company/careers/open-positions") == "databricks"
    assert boards.site_token("https://careers.airbnb.com/positions/") == "airbnb"
    assert boards.site_token("https://acme-robotics.com/careers") == "acme-robotics"
    assert boards.site_token("https://a_b.com/careers") is None
    assert boards.site_token("not a link") is None


def test_board_keys() -> None:
    assert boards.key("greenhouse", "stripe") == "stripe"
    assert boards.key("lever", "palantir") == "lever:palantir"
    assert [boards.company(b) for b in ("stripe", "lever:palantir", "ashby:openai")] == ["stripe", "palantir", "openai"]
