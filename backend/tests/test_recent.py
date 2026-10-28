from app.recent import Recent


def test_the_least_recently_used_entry_goes_first() -> None:
    recent: Recent[str, int] = Recent(capacity=2)
    recent.put("a", 1)
    recent.put("b", 2)
    assert recent.get("a") == 1  # "a" is now the most recent
    recent.put("c", 3)
    assert "b" not in recent
    assert (recent.get("a"), recent.get("c"), len(recent)) == (1, 3, 2)
    assert recent.get("missing") is None
