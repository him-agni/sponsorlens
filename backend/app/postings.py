"""A job posting from any board, and the US-location check every board shares."""

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Posting:
    # "<board>:<company>:<job id>", e.g. greenhouse:stripe:8172508 or lever:palantir:6ed76ce8-...
    source: str
    company: str
    title: str
    url: str
    location: str
    text: str


# DE and IN are left out: they are also the country codes for Germany and India ("Berlin, DE").
_STATES = (
    "AL AK AZ AR CA CO CT DC FL GA HI ID IL IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
    "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()
_US = re.compile(
    r"United States|\bUSA?\b|\bU\.S\.|"
    r"New York|San Francisco|Seattle|Austin|Boston|Chicago|Los Angeles|Denver|Atlanta|Washington,? D\.?C|"
    rf",\s*(?:{'|'.join(_STATES)})\b"
)


def in_us(places: Iterable[str]) -> bool:
    """True if any of these place names is in the US, for boards that give locations only as text."""
    return any(_US.search(place or "") for place in places)
