import html
import re

from bs4 import BeautifulSoup

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})
_DASHES = re.compile(r"[‐-―]")
_BLOCKS = ["p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"]
_SPACE = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")
_ANY_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Plain text that model quotes are checked against.

    Line breaks are kept, so headings and bullets stay separate from the sentences around them.
    Greenhouse escapes its HTML, so entities are unescaped before tags are stripped.
    """
    text = html.unescape(text)
    if "<" in text:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all(_BLOCKS):
            tag.insert_after("\n")
        text = soup.get_text()
    text = _DASHES.sub("-", text.translate(_QUOTES))
    lines = (_SPACE.sub(" ", line).strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def quote_in_text(quote: str, normalized_text: str) -> bool:
    """A quote is verified when it appears verbatim, ignoring case, quote style, spacing and line breaks."""
    quote = _ANY_SPACE.sub(" ", normalize(quote)).strip(" \"'").rstrip(".")
    return bool(quote) and quote.casefold() in _ANY_SPACE.sub(" ", normalized_text).casefold()
