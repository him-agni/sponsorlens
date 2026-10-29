from app.ashby import is_us, parse_board


def place(country: str | None, location: str = "") -> dict:
    address = {"postalAddress": {"addressCountry": country}} if country else None
    return {"location": location, "address": address}


def job(id: str, *, country: str | None = "United States", secondary=(), listed=True, published="2026-10-01", pay=None) -> dict:
    return {
        "id": id,
        "title": f"Engineer {id}",
        "jobUrl": f"https://jobs.ashbyhq.com/acme/{id}",
        "isListed": listed,
        "publishedAt": published,
        "descriptionHtml": "<p>We do not sponsor visas.</p>",
        "compensation": {"compensationTierSummary": pay} if pay else None,
        "shouldDisplayCompensationOnJobPostings": bool(pay),
        "secondaryLocations": list(secondary),
        **place(country, "San Francisco"),
    }


def test_any_us_location_counts() -> None:
    assert is_us(job("a"))
    assert not is_us(job("b", country="United Kingdom"))
    assert is_us(job("c", country="United Kingdom", secondary=[place("United States")]))
    # Without addresses, the location text decides.
    assert is_us(job("d", country=None))


def test_parse_keeps_listed_us_jobs_oldest_first_and_adds_the_pay() -> None:
    payload = {
        "jobs": [
            job("new", published="2026-10-20", pay="$150K - $200K"),
            job("hidden", listed=False),
            job("abroad", country="Japan"),
            job("old", published="2026-09-01"),
        ]
    }
    parsed = parse_board("acme", payload)
    assert [p.source for p in parsed] == ["ashby:acme:old", "ashby:acme:new"]
    assert "Compensation: $150K - $200K" in parsed[1].text
    assert "Compensation" not in parsed[0].text
