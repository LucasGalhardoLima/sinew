"""Orchestrate the v1 build: raw inputs -> verses, texts, versification_map, connections
-> dist/sinew.sqlite + dist/parquet/*.parquet + dataset_meta.

Deterministic: reads only vendored raw under data/raw (pinned in sources.lock.json), writes
sorted rows, so re-running reproduces byte-for-byte. Run: `python -m sinew.build` (or `make build`).
"""
import os, json, sqlite3, hashlib, datetime, pathlib
from . import __version__
from .books import BOOK_NUM, BOOK_NAME, testament, parse_id
from .text import load_web
from .text_pt import load_blivre, load_nva
from .versification import build_scheme_map
from .connections import load_cross_references

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DIST = ROOT / "dist"
CANONICAL_BASE = os.environ.get("SINEW_CANONICAL_BASE", "eng")   # eng (default) | org
LICENSE = ("CC-BY-4.0 (compilation; attribution to OpenBible) + Public Domain WEB text "
           "+ CC BY 4.0 Brasil BLIVRE text (attribution to Diego Santos, Mario Sérgio, Marco Teles) "
           "+ CC BY-SA 4.0 NVA text (attribution to the NVA translation team, biblianva.com.br)")

SCHEMA = """
CREATE TABLE verses (
  verse_id TEXT PRIMARY KEY, book TEXT, chapter INTEGER, verse INTEGER,
  canonical_order INTEGER, tier INTEGER);
CREATE TABLE books (
  book TEXT PRIMARY KEY, name TEXT, testament TEXT, book_number INTEGER, chapter_count INTEGER);
CREATE TABLE texts (
  verse_id TEXT, translation TEXT, text TEXT, tier INTEGER,
  PRIMARY KEY (verse_id, translation));
CREATE TABLE versification_map (
  verse_id TEXT, scheme TEXT, scheme_ref TEXT, status TEXT, tier INTEGER);
CREATE TABLE connections (
  source_verse_id TEXT, target_verse_id TEXT, type TEXT, source TEXT,
  weight INTEGER, confidence REAL, review_status TEXT, turpie_class TEXT, tier INTEGER);
CREATE TABLE dataset_meta (key TEXT PRIMARY KEY, value TEXT);
"""
INDEXES = [
    "CREATE INDEX ix_texts_verse ON texts(verse_id)",
    "CREATE INDEX ix_vmap_verse ON versification_map(verse_id)",
    "CREATE INDEX ix_vmap_scheme ON versification_map(scheme, scheme_ref)",
    "CREATE INDEX ix_conn_src ON connections(source_verse_id)",
    "CREATE INDEX ix_conn_tgt ON connections(target_verse_id)",
    "CREATE INDEX ix_conn_type ON connections(type)",
]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_versification_rows(verses):
    """Per eng verse: an identity 'eng' row + an 'org' (Hebrew) row via the Copenhagen map.
    lxx is deferred to P1 (see README). Returns sorted rows + the flagged mapping entries."""
    eng = json.load(open(RAW / "cph_eng.json"))
    eng_to_org, flagged = build_scheme_map(eng["mappedVerses"])
    rows = []
    for book, chap, verse, _order in verses:
        vid = f"{book}.{chap}.{verse}"
        rows.append((vid, "eng", vid, "present", 1))
        hit = eng_to_org.get((book, chap, verse))
        ob, oc, ov, st = hit if hit else (book, chap, verse, "present")
        rows.append((vid, "org", f"{ob}.{oc}.{ov}", st, 1))
    rows.sort(key=lambda r: (BOOK_NUM[r[0].split(".")[0]], int(r[0].split(".")[1]),
                             int(r[0].split(".")[2]), r[1]))
    return rows, flagged


def write_sqlite(path, verses, books_rows, texts, vmap, edges, meta):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO verses VALUES (?,?,?,?,?,1)",
                    ((f"{b}.{c}.{v}", b, c, v, o) for b, c, v, o in verses))
    con.executemany("INSERT INTO books VALUES (?,?,?,?,?)", books_rows)
    con.executemany("INSERT INTO texts VALUES (?,?,?,1)", texts)
    con.executemany("INSERT INTO versification_map VALUES (?,?,?,?,?)", vmap)
    con.executemany("INSERT INTO connections VALUES (?,?,?,?,?,?,?,?,2)", edges)
    con.executemany("INSERT INTO dataset_meta VALUES (?,?)", meta)
    for ix in INDEXES:
        con.execute(ix)
    con.commit()
    con.close()


def export_parquet(sqlite_path, out_dir):
    import pyarrow as pa, pyarrow.parquet as pq
    # Explicit types for columns that are all-NULL in v1 but get populated in P1, so the
    # published Parquet schema stays stable across versions (no null->string/double break).
    type_hints = {"confidence": pa.float64(), "turpie_class": pa.string()}
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        rows = con.execute(f"SELECT * FROM {t}").fetchall()
        cols = [d[0] for d in con.execute(f"SELECT * FROM {t} LIMIT 0").description]
        table = pa.table({c: pa.array([r[c] for r in rows], type=type_hints.get(c)) for c in cols})
        pq.write_table(table, out_dir / f"{t}.parquet")
    con.close()
    return tables


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    verses, texts, counts = load_web(RAW / "web.json")
    verse_set = {f"{b}.{c}.{v}" for b, c, v, _ in verses}

    blivre_texts, blivre_stats = load_blivre(RAW / "blivre_n4_vpl.txt", verse_set, counts)
    texts += blivre_texts

    nva_texts, nva_stats = load_nva(RAW / "nva_pt.json", verse_set, counts)
    texts += nva_texts

    # books table (Tier-1 metadata)
    chapters_per_book = {}
    for b, c, _v, _o in verses:
        chapters_per_book[b] = max(chapters_per_book.get(b, 0), c)
    books_rows = sorted(
        [(b, BOOK_NAME[b], testament(b), BOOK_NUM[b], chapters_per_book[b]) for b in chapters_per_book],
        key=lambda r: r[3])

    vmap, vflagged = build_versification_rows(verses)
    edges, stats = load_cross_references(RAW / "openbible_cross_references.txt", verse_set, counts)

    lock = json.load(open(ROOT / "sources.lock.json"))
    meta = [
        ("name", "sinew"),
        ("version", __version__),
        ("build_date", datetime.datetime.now(datetime.timezone.utc).date().isoformat()),
        ("canonical_base", CANONICAL_BASE),
        ("license", LICENSE),
        ("verse_count", str(len(verses))),
        ("text_count", str(len(texts))),
        ("text_translations", "WEB,BLIVRE,NVA"),
        ("text_blivre_coverage", f"{blivre_stats['inserted']}/{len(verses)}"),
        ("text_blivre_skipped", json.dumps({k: v for k, v in blivre_stats.items() if k != "inserted"})),
        ("text_nva_coverage", f"{nva_stats['inserted']}/{len(verses)}"),
        ("text_nva_skipped", json.dumps({k: v for k, v in nva_stats.items() if k != "inserted"})),
        ("connection_count", str(len(edges))),
        ("connection_unresolved", str(stats["unresolved"])),
        ("versification_schemes", "eng,org"),
        ("versification_flagged", str(len(vflagged))),
        ("source_pins", json.dumps({k: v["sha256"] for k, v in lock["sources"].items()})),
        ("attribution", "Cross-references: OpenBible.info (CC-BY). Text: World English Bible (Public Domain); "
                        "Bíblia Livre (BLIVRE), CC BY 4.0 Brasil — Diego Santos, Mario Sérgio, Marco Teles; "
                        "Nova Bíblia de Acesso Livre (NVA), CC BY-SA 4.0 — biblianva.com.br."),
    ]

    db = DIST / "sinew.sqlite"
    write_sqlite(db, verses, books_rows, texts, vmap, edges, meta)
    tables = export_parquet(db, DIST / "parquet")

    print(f"verses={len(verses):,}  texts={len(texts):,}  versification_rows={len(vmap):,}"
          f"  (flagged map entries={len(vflagged)})")
    print(f"BLIVRE: parsed={blivre_stats['parsed']:,}  inserted={blivre_stats['inserted']:,}"
          f"  unaddressable={blivre_stats['unaddressable']:,}  placeholder={blivre_stats['placeholder']:,}")
    print(f"NVA: parsed={nva_stats['parsed']:,}  inserted={nva_stats['inserted']:,}"
          f"  unaddressable={nva_stats['unaddressable']:,}")
    print(f"connections: rows={stats['rows']:,} -> edges={len(edges):,}"
          f"  (ok={stats['ok']:,}  unresolved={stats['unresolved']:,}"
          f"  self-skipped={stats['self_skipped']:,}  bad_rows={stats['bad_rows']:,})")
    print(f"wrote {db.relative_to(ROOT)} ({db.stat().st_size//1024:,} KB)  +  parquet: {', '.join(tables)}")
    print(f"db sha256: {_sha256(db)}")


if __name__ == "__main__":
    main()
