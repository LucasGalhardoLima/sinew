"""Export the dataset into a static, offline front-end: the two 'telescope' views.

Reads dist/sinew.sqlite (read-only, via sinew.query.connect) and writes dist/viz/:

    index.html              HERO: the meaning-terrain view (meaning.html) with meaning.json inlined,
                            so it works straight from file://. Falls back to the chord view if no
                            meaning layer has been built (see sinew.embed / `make embed`).
    chord.html              the radial chord diagram, with `books.json` inlined (drill-down needs serve)
    sinew.viz.js            chord-diagram logic   (copied from committed src/sinew/viz/)
    meaning.viz.js          meaning-terrain logic (copied; only when a meaning layer exists)
    vendor/d3.v7.min.js     vendored, pinned D3 (copied; sha256 in sources.lock.json)
    data/books.json         macro: 66 book nodes + book-pair aggregated edges (review_status='ok')
    data/texts.json         {verse_id: WEB text} — one shared map for hover tooltips
    data/book/<Book>.json   per-source-book verse-level edges, lazy-loaded on drill-down
    data/meaning.json       Tier-3 meaning layer (chapter layout + surprising arcs), copied verbatim
                            from the committed src/sinew/viz/data/meaning.json — no torch at viz time

Authoritative arcs are Tier-2 sourced edges with review_status='ok' only; `type`/`source` are kept on
every edge as first-class facets. The meaning terrain's POSITIONS are Tier-3 (computed, not authoritative);
its arcs stay Tier-2 sourced. Deterministic: explicit ORDER BY, sorted JSON keys, no volatile fields;
offline (D3 vendored, meaning.json precomputed/committed). Run: `python -m sinew.export_viz` (or `make viz`).
"""
import json
import shutil
import pathlib

from . import query
from .books import BOOKS, testament

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
VIZ_SRC = pathlib.Path(__file__).resolve().parent / "viz"   # committed front-end source
MEANING_SRC = VIZ_SRC / "data" / "meaning.json"             # committed Tier-3 layer (built by sinew.embed)


def _dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def books_payload(con):
    """Macro payload: 66 nodes (canonical order) + book-pair aggregated `ok` edges, with facet meta."""
    nodes = [
        {"book": r["book"], "name": r["name"], "testament": r["testament"],
         "book_number": r["book_number"], "chapter_count": r["chapter_count"]}
        for r in con.execute(
            "SELECT book, name, testament, book_number, chapter_count FROM books ORDER BY book_number")
    ]
    edges, facets = [], set()
    for r in con.execute(
        "SELECT vs.book AS source_book, vt.book AS target_book, c.type AS type, c.source AS source, "
        "       SUM(c.weight) AS sum_weight, COUNT(*) AS edge_count "
        "FROM connections c "
        "JOIN verses vs ON vs.verse_id=c.source_verse_id "
        "JOIN verses vt ON vt.verse_id=c.target_verse_id "
        "WHERE c.review_status='ok' "
        "GROUP BY vs.book, vt.book, c.type, c.source "
        "ORDER BY vs.book, vt.book, c.type, c.source"
    ):
        edges.append({
            "source_book": r["source_book"], "target_book": r["target_book"],
            "type": r["type"], "source": r["source"],
            "sum_weight": r["sum_weight"], "edge_count": r["edge_count"],
            "cross_testament": testament(r["source_book"]) != testament(r["target_book"]),
        })
        facets.add((r["type"], r["source"]))
    meta = {
        "review_status": "ok",
        "edge_count_total": sum(e["edge_count"] for e in edges),
        "facets": [{"type": t, "source": s} for t, s in sorted(facets)],
    }
    return {"meta": meta, "nodes": nodes, "edges": edges}


def book_detail(con, book):
    """Per-source-book payload: verse-level outgoing `ok` edges (short keys s/t/w + type/source)."""
    edges = [
        {"s": r["source_verse_id"], "t": r["target_verse_id"], "w": r["weight"],
         "type": r["type"], "source": r["source"]}
        for r in con.execute(
            "SELECT c.source_verse_id, c.target_verse_id, c.weight, c.type, c.source "
            "FROM connections c JOIN verses vs ON vs.verse_id=c.source_verse_id "
            "WHERE vs.book=? AND c.review_status='ok' "
            "ORDER BY c.source_verse_id, c.target_verse_id, c.type, c.source",
            (book,),
        )
    ]
    return {"book": book, "review_status": "ok", "edges": edges}


def texts_payload(con):
    """One shared {verse_id: WEB text} map — dedupes hover text across all per-book files."""
    return {r["verse_id"]: r["text"]
            for r in con.execute("SELECT verse_id, text FROM texts WHERE translation='WEB'")}


def _inline(src_html, placeholder, var, payload):
    """Read a committed viz HTML and replace `placeholder` with `window.<var>=<payload>;` (file:// hero)."""
    inline = (f"<script>window.{var}="
              + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";</script>")
    return (VIZ_SRC / src_html).read_text(encoding="utf-8").replace(placeholder, inline)


def _copy_frontend(out_dir, books_json, meaning_json):
    """Lay out the front-end. With a meaning layer, the terrain is the hero `index.html` and the chord
    diagram is `chord.html`; without it, the chord diagram stays the hero `index.html` (graceful fallback)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "vendor").mkdir(exist_ok=True)
    shutil.copyfile(VIZ_SRC / "vendor" / "d3.v7.min.js", out_dir / "vendor" / "d3.v7.min.js")
    shutil.copyfile(VIZ_SRC / "sinew.viz.js", out_dir / "sinew.viz.js")
    chord_html = _inline("index.html", "<!--SINEW_BOOKS-->", "SINEW_BOOKS", books_json)
    if meaning_json is not None:
        shutil.copyfile(VIZ_SRC / "meaning.viz.js", out_dir / "meaning.viz.js")
        (out_dir / "chord.html").write_text(chord_html, encoding="utf-8")
        (out_dir / "index.html").write_text(
            _inline("meaning.html", "<!--SINEW_MEANING-->", "SINEW_MEANING", meaning_json), encoding="utf-8")
    else:
        (out_dir / "index.html").write_text(chord_html, encoding="utf-8")


def _load_meaning():
    """The committed Tier-3 meaning layer, or None if `make embed` was never run. Read-only, no torch."""
    if not MEANING_SRC.exists():
        return None
    with open(MEANING_SRC, encoding="utf-8") as f:
        return json.load(f)


def export_viz(sqlite_path=None, out_dir=None):
    """Write the full viz bundle. Returns a small stats dict. Deterministic & offline."""
    out_dir = pathlib.Path(out_dir) if out_dir else (DIST / "viz")
    meaning_json = _load_meaning()
    con = query.connect(sqlite_path)
    try:
        books_json = books_payload(con)
        _copy_frontend(out_dir, books_json, meaning_json)
        _dump(books_json, out_dir / "data" / "books.json")
        _dump(texts_payload(con), out_dir / "data" / "texts.json")
        for book in BOOKS:
            _dump(book_detail(con, book), out_dir / "data" / "book" / f"{book}.json")
    finally:
        con.close()
    if meaning_json is not None:                       # copy verbatim so served bytes == committed bytes
        (out_dir / "data").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MEANING_SRC, out_dir / "data" / "meaning.json")
    return {
        "books": len(books_json["nodes"]),
        "edges": len(books_json["edges"]),
        "cross_testament_edges": sum(e["edge_count"] for e in books_json["edges"] if e["cross_testament"]),
        "meaning_nodes": len(meaning_json["nodes"]) if meaning_json else 0,
        "meaning_links": sum(len(r) for r in meaning_json["links"]) if meaning_json else 0,
    }


def main():
    out = DIST / "viz"
    stats = export_viz(out_dir=out)
    print(f"viz: {stats['books']} book nodes, {stats['edges']:,} book-pair edges, "
          f"{stats['cross_testament_edges']:,} cross-Testament edges -> {out.relative_to(ROOT)}")
    if stats["meaning_nodes"]:
        print(f"meaning view (hero): {stats['meaning_nodes']:,} chapter nodes, "
              f"{stats['meaning_links']:,} on-demand cross-ref links · chord view at chord.html")
    else:
        print("no meaning layer (run `make embed` to add the terrain); chord view is the hero.")
    print(f"open {(out / 'index.html')} (hero, file://), or `make viz-serve` for the drill-down.")


if __name__ == "__main__":
    main()
