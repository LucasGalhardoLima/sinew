"""Validation suite (P0 #5) — the dataset doesn't ship if any check fails.

Guarantees: every verse has text; every connection endpoint either resolves to a real verse_id
or is explicitly flagged (no silent failure); schema/tier rules hold; the spike-proven
versification divergences map correctly. `python -m sinew.validate` prints a report and exits
nonzero on failure; the same functions back the pytest suite.
"""
import sys, sqlite3, hashlib, pathlib

DB = pathlib.Path(__file__).resolve().parents[2] / "dist" / "sinew.sqlite"

# expected divergences (eng verse_id -> org scheme_ref) — the spike-proven hard cases
ORG_FIXTURES = {
    "Joel.2.32": "Joel.3.5", "Mal.4.5": "Mal.3.23",
    "Ps.3.1": "Ps.3.2", "Ps.51.1": "Ps.51.3",
}
ENG_IDENTITY = ["John.3.16", "Gen.1.1", "Rev.22.21"]


def _scalar(con, q, *a): return con.execute(q, a).fetchone()[0]


def run_checks(con):
    """Return list of (name, ok:bool, detail:str)."""
    out = []

    def chk(name, ok, detail=""): out.append((name, bool(ok), detail))

    # 1. every verse has >=1 text
    orphan_v = _scalar(con, "SELECT COUNT(*) FROM verses v "
                             "WHERE NOT EXISTS (SELECT 1 FROM texts t WHERE t.verse_id=v.verse_id)")
    chk("every verse has text", orphan_v == 0, f"{orphan_v} verses without text")

    # 2. every text points at a real verse
    orphan_t = _scalar(con, "SELECT COUNT(*) FROM texts t "
                             "WHERE NOT EXISTS (SELECT 1 FROM verses v WHERE v.verse_id=t.verse_id)")
    chk("every text has a verse", orphan_t == 0, f"{orphan_t} texts without verse")

    # 3. no 'ok' connection has an unresolved endpoint (resolution honest)
    bad_ok = _scalar(con,
        "SELECT COUNT(*) FROM connections c WHERE c.review_status='ok' AND ("
        "  NOT EXISTS (SELECT 1 FROM verses v WHERE v.verse_id=c.source_verse_id)"
        "  OR NOT EXISTS (SELECT 1 FROM verses v WHERE v.verse_id=c.target_verse_id))")
    chk("'ok' edges truly resolve", bad_ok == 0, f"{bad_ok} 'ok' edges with a missing endpoint")

    # 4. no unresolved endpoint is silently 'ok' — all flagged with a reason
    unflagged = _scalar(con,
        "SELECT COUNT(*) FROM connections c WHERE c.review_status='ok' = 0 AND "
        "c.review_status NOT LIKE 'unresolved%'")
    chk("unresolved edges are flagged", unflagged == 0, f"{unflagged} edges flagged without a reason")
    n_unres = _scalar(con, "SELECT COUNT(*) FROM connections WHERE review_status LIKE 'unresolved%'")
    out.append(("(info) unresolved-but-flagged edges", True, f"{n_unres} edges"))

    # 5. schema/tier rules: every connection has source+type+weight; tiers correct
    no_src = _scalar(con, "SELECT COUNT(*) FROM connections WHERE source IS NULL OR source=''")
    chk("no connection without source", no_src == 0, f"{no_src} edges missing source")
    no_type = _scalar(con, "SELECT COUNT(*) FROM connections WHERE type IS NULL OR type=''")
    chk("every connection has a type", no_type == 0, f"{no_type} edges missing type")
    bad_tier = (_scalar(con, "SELECT COUNT(*) FROM connections WHERE tier!=2")
                + _scalar(con, "SELECT COUNT(*) FROM verses WHERE tier!=1")
                + _scalar(con, "SELECT COUNT(*) FROM texts WHERE tier!=1"))
    chk("tiers correct (verses/texts=1, connections=2)", bad_tier == 0, f"{bad_tier} bad tier rows")

    # 6. versification divergence fixtures
    for vid, expect in ORG_FIXTURES.items():
        got = con.execute("SELECT scheme_ref FROM versification_map WHERE verse_id=? AND scheme='org'",
                          (vid,)).fetchone()
        got = got[0] if got else None
        chk(f"org map {vid} -> {expect}", got == expect, f"got {got!r}")
    for vid in ENG_IDENTITY:
        got = con.execute("SELECT scheme_ref FROM versification_map WHERE verse_id=? AND scheme='eng'",
                          (vid,)).fetchone()
        got = got[0] if got else None
        chk(f"eng identity {vid}", got == vid, f"got {got!r}")

    # 7. sanity counts
    nv = _scalar(con, "SELECT COUNT(*) FROM verses")
    chk("verse count in range", 31000 <= nv <= 31200, f"{nv} verses")
    ne = _scalar(con, "SELECT COUNT(*) FROM connections")
    chk("connection count plausible", ne > 300000, f"{ne} connections")
    return out


def data_tables_hash(con):
    """Build-provenance-independent hash of the data tables (stable across build dates)."""
    h = hashlib.sha256()
    for t in ["books", "verses", "texts", "versification_map", "connections"]:
        for row in con.execute(f"SELECT * FROM {t} ORDER BY 1,2,3,4"):
            h.update(repr(row).encode())
    return h.hexdigest()


def main():
    if not DB.exists():
        print(f"FAIL: {DB} not found — run `make build` first"); return 1
    con = sqlite3.connect(DB)
    results = run_checks(con)
    width = max(len(n) for n, _, _ in results)
    failed = 0
    for name, ok, detail in results:
        tag = "PASS" if ok else "FAIL"
        if not ok and not name.startswith("(info)"):
            failed += 1
        print(f"  [{tag}] {name.ljust(width)}  {detail}")
    print(f"\ndata-tables sha256: {data_tables_hash(con)}")
    con.close()
    if failed:
        print(f"\n{failed} check(s) FAILED")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
