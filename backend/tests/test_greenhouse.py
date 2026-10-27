import httpx

from app.greenhouse import fetch_board, is_us, parse_board


def job(id: int, location: str, offices: list[str] | None = None, content: str = "&lt;p&gt;Hi&lt;/p&gt;") -> dict:
    return {
        "id": id,
        "title": f"Engineer {id}",
        "company_name": "Acme",
        "absolute_url": f"https://job-boards.greenhouse.io/acme/jobs/{id}",
        "location": {"name": location},
        "offices": [{"name": o, "location": o} for o in offices or []],
        "content": content,
    }


def test_us_locations_are_recognized() -> None:
    for location in ["Remote - United States", "Hybrid - San Francisco", "Austin, TX", "New York, NY; London", "USA"]:
        assert is_us(job(1, location)), location
    for location in ["Remote - Germany", "Hybrid - London, Berlin", "Toronto, Canada", "Sydney", "Bengaluru, IN", "Berlin, DE"]:
        assert not is_us(job(1, location)), location


def test_an_office_in_the_us_counts() -> None:
    assert is_us(job(1, "Hybrid", offices=["Seattle, Washington, United States"]))


def test_parse_keeps_us_jobs_oldest_first() -> None:
    payload = {"jobs": [job(3, "Austin, TX"), job(1, "London"), job(2, "Remote - US"), job(4, "Boston", content="")]}
    postings = parse_board("acme", payload)
    assert [p.source for p in postings] == ["greenhouse:acme:2", "greenhouse:acme:3"]
    assert postings[0].company == "Acme"
    assert postings[0].url.endswith("/2")


async def test_fetch_asks_for_content() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"jobs": [job(1, "Austin, TX")]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        postings = await fetch_board(client, "acme")
    assert seen["url"] == "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"
    assert len(postings) == 1
