"""End-to-end dataset integrity tests (run against the built dist/sinew.sqlite)."""
import pytest
from sinew.validate import run_checks
from sinew.versification import build_scheme_map
from sinew.books import parse_cph_ref
from sinew.text_pt import load_blivre, _clean, BLIVRE_TO_SINEW, load_nva, NVA_TO_SINEW


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


def test_blivre_text_roundtrip(con):
    t = con.execute("SELECT text FROM texts WHERE verse_id='Gen.1.1' AND translation='BLIVRE'").fetchone()
    assert t and "princípio" in t[0].lower()


def test_blivre_coverage_is_near_complete(con):
    """BLIVRE covers WEB's canonical set almost 1:1 -- the only gaps are the well-known
    TR-vs-critical-text disputed verses (Matt 17:21, Mark 16 longer ending fragments, Rom
    16:24-27, ...), never a versification-alignment bug. See text_pt.py's docstring."""
    n_web = con.execute("SELECT COUNT(*) FROM texts WHERE translation='WEB'").fetchone()[0]
    n_blivre = con.execute("SELECT COUNT(*) FROM texts WHERE translation='BLIVRE'").fetchone()[0]
    assert n_blivre / n_web > 0.999, f"BLIVRE coverage dropped: {n_blivre}/{n_web}"


def test_blivre_book_mapping_spot_checks(con):
    """A handful of verses spread across the canon, checked for an expected Portuguese keyword
    -- catches a wholesale book/chapter mis-map (e.g. BLIVRE_TO_SINEW swapping two codes) that
    a coverage-ratio check alone wouldn't."""
    fixtures = {
        "Gen.1.1": "princípio",
        "Ps.23.1": "pastor",
        "Isa.9.6": "filho",
        "John.3.16": "amou",
        "Rom.8.28": "propósito",
        "Rev.22.21": "graça",
    }
    for vid, expected_word in fixtures.items():
        row = con.execute(
            "SELECT text FROM texts WHERE verse_id=? AND translation='BLIVRE'", (vid,)
        ).fetchone()
        assert row is not None, f"expected BLIVRE coverage at {vid}"
        assert expected_word in row[0].lower(), f"{vid}: expected {expected_word!r} in {row[0]!r}"


def test_nva_text_roundtrip(con):
    t = con.execute("SELECT text FROM texts WHERE verse_id='Gen.1.1' AND translation='NVA'").fetchone()
    assert t and "princípio" in t[0].lower()


def test_nva_coverage_is_near_complete(con):
    """NVA covers WEB's canonical set almost 1:1 -- the only gaps are the four well-known
    textual/versification variants in KNOWN_DIVERGENT_CHAPTERS_NVA, never a mapping bug.
    See text_pt.py's docstring."""
    n_web = con.execute("SELECT COUNT(*) FROM texts WHERE translation='WEB'").fetchone()[0]
    n_nva = con.execute("SELECT COUNT(*) FROM texts WHERE translation='NVA'").fetchone()[0]
    assert n_nva / n_web > 0.999, f"NVA coverage dropped: {n_nva}/{n_web}"


def test_nva_book_mapping_spot_checks(con):
    """Same fixture verses as the BLIVRE spot-check, same expected keywords -- both pt-BR
    translations should agree on these common words even though wording differs elsewhere."""
    fixtures = {
        "Gen.1.1": "princípio",
        "Ps.23.1": "pastor",
        "Isa.9.6": "filho",
        "John.3.16": "amou",
        "Rom.8.28": "propósito",
        "Rev.22.21": "graça",
    }
    for vid, expected_word in fixtures.items():
        row = con.execute(
            "SELECT text FROM texts WHERE verse_id=? AND translation='NVA'", (vid,)
        ).fetchone()
        assert row is not None, f"expected NVA coverage at {vid}"
        assert expected_word in row[0].lower(), f"{vid}: expected {expected_word!r} in {row[0]!r}"


def test_nva_book_mapping_is_bijective_onto_sinew_canon():
    from sinew.books import BOOK_NUM
    assert len(NVA_TO_SINEW) == 66
    assert set(NVA_TO_SINEW.values()) == set(BOOK_NUM.keys())
    assert len(set(NVA_TO_SINEW.values())) == 66   # no two NVA codes collide on one abbrev


def test_nva_versification_drift_fails_loud(tmp_path):
    """A chapter-count mismatch NOT in KNOWN_DIVERGENT_CHAPTERS_NVA must raise, not silently
    misalign text -- the guard against a future NVA re-fetch drifting unnoticed."""
    import json as _json
    raw = tmp_path / "fake.json"
    raw.write_text(_json.dumps([
        {"abbrev": "gn", "name": "Gênesis",
         "chapters": [{"number": 1, "verses": [{"number": 1, "text": "texto um"},
                                                 {"number": 2, "text": "texto dois"}]}]}
    ]), encoding="utf-8")
    verse_set = {"Gen.1.1", "Gen.1.2"}
    web_counts_ok = {("Gen", 1): 2}
    load_nva(str(raw), verse_set, web_counts_ok)   # matches -> no raise

    web_counts_drifted = {("Gen", 1): 3}            # WEB says 3 verses, fake source has 2
    with pytest.raises(AssertionError):
        load_nva(str(raw), verse_set, web_counts_drifted)


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


def test_blivre_book_mapping_is_bijective_onto_sinew_canon():
    from sinew.books import BOOK_NUM
    assert len(BLIVRE_TO_SINEW) == 66
    assert set(BLIVRE_TO_SINEW.values()) == set(BOOK_NUM.keys())
    assert len(set(BLIVRE_TO_SINEW.values())) == 66   # no two BLIVRE codes collide on one abbrev


def test_blivre_clean_fixes_export_artifacts():
    # supplied-word brackets removed
    assert _clean("guarda o teu coração; porque dele [procedem] as saídas") == \
        "guarda o teu coração; porque dele procedem as saídas"
    # hyphen-elision split across a bracket rejoined ("dá- [la]" -> "dá-la")
    assert _clean("vou dá- [la] a vós") == "vou dá-la a vós"
    # missing space after a glued psalm title
    assert _clean("Salmo de Davi:O SENHOR é meu pastor") == "Salmo de Davi: O SENHOR é meu pastor"
    # untouched when there's nothing to fix
    assert _clean("Confia no SENHOR com todo o teu coração.") == "Confia no SENHOR com todo o teu coração."


def test_blivre_versification_drift_fails_loud(tmp_path):
    """A chapter-count mismatch NOT in KNOWN_DIVERGENT_CHAPTERS must raise, not silently
    misalign text -- this is the guard against a future BLIVRE re-fetch drifting unnoticed."""
    vpl = tmp_path / "fake.txt"
    vpl.write_text("GEN 1:1 texto um\nGEN 1:2 texto dois\n", encoding="utf-8")
    verse_set = {"Gen.1.1", "Gen.1.2"}
    web_counts_ok = {("Gen", 1): 2}
    load_blivre(str(vpl), verse_set, web_counts_ok)   # matches -> no raise

    web_counts_drifted = {("Gen", 1): 3}               # WEB says 3 verses, fake source has 2
    with pytest.raises(AssertionError):
        load_blivre(str(vpl), verse_set, web_counts_drifted)
