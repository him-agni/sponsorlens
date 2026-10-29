import httpx

from app.lever import fetch_job, is_us, parse_board


def posting(id: str, *, country: str | None = "US", location: str = "Denver, CO", created: int = 0) -> dict:
    return {
        "id": id,
        "text": f"Engineer {id}",
        "hostedUrl": f"https://jobs.lever.co/acme/{id}",
        "country": country,
        "createdAt": created,
        "categories": {"location": location, "allLocations": [location]},
        "description": "<p>About the role.</p>",
        "lists": [{"text": "What you will do", "content": "<li>Build things</li>"}],
        "additional": "<p>We are unable to sponsor visas.</p>",
    }


def test_the_country_decides_and_location_text_is_the_fallback() -> None:
    assert is_us(posting("a"))
    assert not is_us(posting("b", country="SG", location="Singapore"))
    assert is_us(posting("c", country=None, location="Austin, TX"))
    assert not is_us(posting("d", country=None, location="London, UK"))


def test_parse_keeps_us_postings_oldest_first_with_every_section() -> None:
    payload = [posting("new", created=20), posting("abroad", country="GB", created=5), posting("old", created=10)]
    parsed = parse_board("acme", payload)
    assert [p.source for p in parsed] == ["lever:acme:old", "lever:acme:new"]
    # The closing section is where Lever postings usually state sponsorship.
    for part in ("About the role", "What you will do", "Build things", "unable to sponsor"):
        assert part in parsed[0].text
    assert parsed[0].url == "https://jobs.lever.co/acme/old"


async def test_one_posting_comes_from_the_api() -> None:
    seen = {}
    job_id = "6ed76ce8-4156-4b60-b120-403538bd66cd"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=posting(job_id))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        job = await fetch_job(client, "acme", job_id)
    assert seen["url"] == f"https://api.lever.co/v0/postings/acme/{job_id}?mode=json"
    assert job.title == f"Engineer {job_id}"
