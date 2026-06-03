"""Tests for the telescope export (sinew.export_viz): node count, the cross-Testament thesis totals,
Isaiah's drill-down detail, the shipped front-end, and determinism."""
import json

from sinew.export_viz import export_viz
from sinew.books import testament as _testament   # aliased: pytest would collect a bare `testament` (test*)


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_export_viz(con, tmp_path):           # `con` ensures dist/sinew.sqlite is built
    out = tmp_path / "viz"
    stats = export_viz(out_dir=out)
    books = _load(out / "data" / "books.json")

    # 66 book nodes
    assert len(books["nodes"]) == 66 and stats["books"] == 66

    # cross-Testament thesis: NT→OT 56,786 + OT→NT 72,193 = 128,979
    xt = [e for e in books["edges"] if e["cross_testament"]]
    assert sum(e["edge_count"] for e in xt) == 128979
    assert stats["cross_testament_edges"] == 128979

    def dirsum(s, t):
        return sum(e["edge_count"] for e in books["edges"]
                   if _testament(e["source_book"]) == s and _testament(e["target_book"]) == t)
    assert dirsum("NT", "OT") == 56786
    assert dirsum("OT", "NT") == 72193

    # facets are first-class (type+source kept on the aggregation)
    assert {"type": "cross_reference", "source": "OpenBible"} in books["meta"]["facets"]
    assert all("type" in e and "source" in e for e in books["edges"])

    # Isaiah per-book detail exists and reaches the Gospels (2,758 edges)
    isa = _load(out / "data" / "book" / "Isa.json")
    gospels = {"Matt", "Mark", "Luke", "John"}
    assert sum(1 for e in isa["edges"] if e["t"].split(".")[0] in gospels) == 2758

    # shared texts map + front-end assets shipped; chord view moved to chord.html, macro inlined there
    texts = _load(out / "data" / "texts.json")
    assert texts["Isa.7.14"] and texts["Matt.1.23"]
    assert (out / "vendor" / "d3.v7.min.js").exists() and (out / "sinew.viz.js").exists()
    assert "window.SINEW_BOOKS=" in (out / "chord.html").read_text(encoding="utf-8")


def test_meaning_view_is_the_hero(con, tmp_path):
    """The committed Tier-3 meaning layer (calm field + on-demand links) is the hero index.html, torch-free."""
    out = tmp_path / "viz"
    stats = export_viz(out_dir=out)

    # the meaning view is the hero; meaning.viz.js + a fetchable meaning.json ship alongside
    assert "window.SINEW_MEANING=" in (out / "index.html").read_text(encoding="utf-8")
    assert (out / "meaning.viz.js").exists()
    assert stats["meaning_nodes"] == 1189 and stats["meaning_links"] >= 1

    meaning = _load(out / "data" / "meaning.json")
    assert meaning["meta"]["tier"] == 3                                  # computed, not authoritative
    assert meaning["meta"]["n_nodes"] == len(meaning["nodes"]) == 1189
    assert "arcs" not in meaning                                         # no global hairball any more

    N = len(meaning["nodes"])
    # node = [meaning_x, meaning_y, kinship_x, kinship_y, color, label, radius, section]
    assert all(len(n) == 8 for n in meaning["nodes"])
    assert all(isinstance(n[k], (int, float)) for n in meaning["nodes"] for k in range(4))

    # links/near are parallel to nodes; links revealed per-chapter on hover, never globally
    assert len(meaning["links"]) == N and len(meaning["near"]) == N
    assert stats["meaning_links"] == sum(len(r) for r in meaning["links"])
    k, n_near = meaning["meta"]["k"], meaning["meta"]["n_near"]
    for row in meaning["links"]:                                         # link = [j, votes, cos_dist]
        assert len(row) <= k
        assert all(0 <= j < N and isinstance(v, int) and 0 <= d <= 2 for j, v, d in row)
    for row in meaning["near"]:                                          # near = [j, ...] (excludes self)
        assert len(row) <= n_near and all(0 <= j < N for j in row)

    # bytes copied verbatim from the committed source (served == committed)
    from sinew.export_viz import MEANING_SRC
    assert (out / "data" / "meaning.json").read_bytes() == MEANING_SRC.read_bytes()


def test_export_is_deterministic(con, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    export_viz(out_dir=a)
    export_viz(out_dir=b)
    for rel in ("data/books.json", "data/texts.json", "data/book/Isa.json", "data/meaning.json"):
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), f"non-deterministic: {rel}"
