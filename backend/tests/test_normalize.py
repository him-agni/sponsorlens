from app.normalize import normalize, quote_in_text


def test_greenhouse_escaped_html() -> None:
    raw = "&lt;p&gt;We &lt;strong&gt;cannot&lt;/strong&gt; sponsor&amp;nbsp;visas.&lt;/p&gt;"
    assert normalize(raw) == "We cannot sponsor visas."


def test_curly_quotes_dashes_and_whitespace() -> None:
    assert normalize("Candidates “must”  be\tUS—based") == 'Candidates "must" be US-based'


def test_line_breaks_keep_headings_apart_from_sentences() -> None:
    assert normalize("Legal\nCandidates must work   without sponsorship.\n\n\n\nEEO") == (
        "Legal\nCandidates must work without sponsorship.\n\nEEO"
    )
    html_text = "<h3>Legal</h3><p>Candidates <b>must</b> work without sponsorship.</p><ul><li>One</li><li>Two</li></ul>"
    assert normalize(html_text) == "Legal\nCandidates must work without sponsorship.\nOne\nTwo"


def test_quote_check_spans_line_breaks() -> None:
    text = normalize("We will not sponsor\nvisas for this role.")
    assert quote_in_text("We will not sponsor visas", text)


def test_quote_check_ignores_case_quotes_and_trailing_period() -> None:
    text = normalize("<p>We don’t sponsor visas now or in the future.</p>")
    assert quote_in_text("we don't sponsor visas now or in the future.", text)
    assert quote_in_text('"We don\'t sponsor visas"', text)


def test_quote_check_rejects_paraphrase() -> None:
    text = normalize("We are unable to sponsor visas.")
    assert not quote_in_text("We cannot sponsor visas", text)
    assert not quote_in_text("", text)
