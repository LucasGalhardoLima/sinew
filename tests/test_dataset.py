"""End-to-end dataset integrity tests (run against the built dist/sinew.sqlite)."""
from sinew.validate import run_checks
from sinew.versification import build_scheme_map
from sinew.books import parse_cph_ref


def test_all_validation_checks_pass(con):
    failures = [(n, d) for n, ok, d in run_checks(con) if not ok and not n.startswith("(info)")]
    assert not failures, f"validation failures: {failures}"


def test_books_and_chapters_complete(con):
    assert con.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 66
    assert con.execute("SELECT COUNT(DISTINCT book||'.'||chapter) FROM verses").fetchone()[0] == 1189


def test_neighbors_query_works(con):
    n = con.execute("SELECT COUNT(*) FROM connections WHERE source_verse_id='John.3.16'").fetchone()[0]
    assert n > 0, "John.3.16 should have outgoing cross-references"


def test_text_roundtrip(con):
    t = con.execute("SELECT text FROM texts WHERE verse_id='Gen.1.1' AND translation='WEB'").fetchone()
    assert t and "beginning" in t[0].lower()


def test_versification_fixtures_unit():
    """Reconciler maps the hard cases without touching the DB (parser-level guard)."""
    import json, pathlib
    raw = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw" / "cph_eng.json"
    m, flagged = build_scheme_map(json.load(open(raw))["mappedVerses"])
    assert flagged == [], f"unexpected unparseable mappings: {flagged}"
    assert m[("Joel", 2, 32)][:3] == ("Joel", 3, 5)
    assert m[("Mal", 4, 5)][:3] == ("Mal", 3, 23)
    assert m[("Ps", 51, 1)][:3] == ("Ps", 51, 3)


def test_cph_ref_parser():
    assert parse_cph_ref("JOL 2:28-32") == [("Joel", 2, v) for v in range(28, 33)]
    assert parse_cph_ref("TOB 1:1") == []   # deuterocanon -> out of scope, empty
