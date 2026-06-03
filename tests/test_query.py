"""Unit tests for the read-only query layer (sinew.query).

Covers the MCP server's acceptance criteria directly at the query layer — no MCP transport and no
optional ``[mcp]`` dependency required. The session ``con`` fixture (conftest.py) builds the DB if
missing; we then open our own read-only connection via ``query.connect()``.
"""
import pytest

from sinew import query
from sinew.query import VerseNotFound


@pytest.fixture(scope="module")
def q(con):                       # depend on session `con` so dist/sinew.sqlite is built if missing
    c = query.connect()           # read-only, row_factory=Row, same dist/sinew.sqlite path
    yield c
    c.close()


def test_get_verse(q):
    v = query.get_verse(q, "John.3.16")
    assert (v["book"], v["chapter"], v["verse"]) == ("John", 3, 16)
    assert v["book_name"] == "John"
    assert "loved" in v["text"].lower()
    assert v["translation"] == "WEB"


def test_cross_references_john_316(q):
    """Acceptance: John.3.16 -> Rom.5.8(968), 1John.4.10/4.9(684), Rom.8.32(497), John.3.15(490)."""
    xr = query.cross_references(q, "John.3.16")
    head = [(r["target_verse_id"], r["weight"]) for r in xr[:5]]
    assert head == [("Rom.5.8", 968), ("1John.4.10", 684), ("1John.4.9", 684),
                    ("Rom.8.32", 497), ("John.3.15", 490)]
    assert all(r["source"] == "OpenBible" for r in xr)         # provenance always present
    assert all(r["review_status"] == "ok" for r in xr)
    assert all(r["target_text"] for r in xr)                   # resolved targets carry text


def test_cross_references_facets(q):
    """type/source are first-class facets and compose; absent facets return nothing (not an error)."""
    assert query.cross_references(q, "John.3.16", type="cross_reference", source="OpenBible")
    assert query.cross_references(q, "John.3.16", type="quotation") == []   # P1 facet, not in v1
    assert len(query.cross_references(q, "John.3.16", limit=3)) == 3
    assert all(r["weight"] >= 400 for r in query.cross_references(q, "John.3.16", min_weight=400))


def test_default_excludes_negative_weight(q):
    """Default min_weight=0 hides disputed negative-weight edges; opting in surfaces them."""
    default = query.cross_references(q, "1Chr.17.27", limit=10000)
    assert len(default) == 3 and all(r["weight"] >= 0 for r in default)
    widened = query.cross_references(q, "1Chr.17.27", min_weight=-1000, limit=10000)
    assert len(widened) == 4
    assert any(r["target_verse_id"] == "Gen.27.33" and r["weight"] == -1 for r in widened)


def test_include_unresolved_never_coerced(q):
    """Unresolved edges are flagged, never coerced to 'ok', and only returned when opted in."""
    ok_only = query.cross_references(q, "Gen.21.33", limit=10000)
    assert len(ok_only) == 15 and all(r["review_status"] == "ok" for r in ok_only)
    full = query.cross_references(q, "Gen.21.33", include_unresolved=True, limit=10000)
    assert len(full) == 16
    flagged = [r for r in full if r["review_status"] != "ok"]
    assert len(flagged) == 1 and flagged[0]["review_status"].startswith("unresolved")
    assert flagged[0]["source"] == "OpenBible"                 # still attributed


def test_back_references(q):
    br = query.back_references(q, "Rom.5.8")
    assert any(r["source_verse_id"] == "John.3.16" for r in br)
    assert all(r["source"] == "OpenBible" for r in br)
    assert all("source_text" in r for r in br)


def test_reconcile_reference(q):
    """Acceptance: Joel.2.32 -> org Joel.3.5; Mal.4.5 -> org Mal.3.23."""
    assert query.reconcile_reference(q, "Joel.2.32", "org")["scheme_ref"] == "Joel.3.5"
    assert query.reconcile_reference(q, "Mal.4.5", "org")["scheme_ref"] == "Mal.3.23"
    assert query.reconcile_reference(q, "John.3.16", "eng")["scheme_ref"] == "John.3.16"   # identity
    with pytest.raises(ValueError):
        query.reconcile_reference(q, "John.3.16", "lxx")       # scheme absent in v1, never fabricated


def test_search_text_is_lexical(q):
    res = query.search_text(q, "In the beginning", limit=5)
    assert any(r["verse_id"] == "Gen.1.1" for r in res)
    assert all(r["translation"] == "WEB" for r in res)


def test_verse_not_found(q):
    with pytest.raises(VerseNotFound):
        query.get_verse(q, "Nope.1.1")          # unknown book
    with pytest.raises(VerseNotFound):
        query.get_verse(q, "John.999.1")        # well-formed but absent
    with pytest.raises(VerseNotFound):
        query.cross_references(q, "garbage")     # malformed id


def test_get_path(q):
    p = query.get_path(q, "John.3.16", "Rom.5.8", max_hops=1)   # direct edge
    assert p["found"] and p["hops"] == 1
    assert p["path"][0]["from"] == "John.3.16" and p["path"][0]["to"] == "Rom.5.8"
    assert p["path"][0]["source"] == "OpenBible"
    assert query.get_path(q, "Gen.1.1", "Gen.1.1")["hops"] == 0  # identity
