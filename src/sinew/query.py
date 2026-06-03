"""Read-only query layer over dist/sinew.sqlite — the single place that reads the dataset.

Plain sqlite3 + parameterized SQL (mirrors validate.py). No mcp/web imports, so it is unit-testable
directly (tests/test_query.py) without the optional ``[mcp]`` dependency, and it is shared by both the
MCP server (``sinew.mcp.server``) and the visualization exporter (``sinew.export_viz``).

Invariants honored here, in one place:
  * every connection row returned carries its provenance (``source`` + ``weight`` + ``review_status``);
  * unresolved edges are never silently coerced to ``ok`` — you must opt in via ``include_unresolved``;
  * connections are *attributed, not asserted*: ``source`` says who lists the link, not that it is true.

Tiers: ``get_verse`` / ``reconcile_reference`` are Tier 1 (facts); ``cross_references`` /
``back_references`` / ``get_path`` are Tier 2 (sourced); ``search_text`` is LEXICAL (NOT semantic —
meaning-based search would be Tier 3). ``type`` and ``source`` are first-class facets on the edge
queries so a future ``quotation`` type (P1) or ``derived_*`` source (Tier 3) is a new facet value,
not a new code path.
"""
import os
import sqlite3
import pathlib

from .books import parse_id

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "dist" / "sinew.sqlite"


class VerseNotFound(ValueError):
    """A verse_id is malformed, names an unknown book, or is absent from the canonical `verses`."""


def connect(db_path=None):
    """Open the dataset strictly read-only. Resolves db_path arg, else $SINEW_DB, else dist/sinew.sqlite."""
    path = pathlib.Path(db_path or os.environ.get("SINEW_DB") or DEFAULT_DB)
    if not path.exists():
        raise FileNotFoundError(
            f"Sinew dataset not found at {path}. Run `make build`, or set $SINEW_DB to the .sqlite path."
        )
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _resolve_verse(con, verse_id):
    """Validate structure (books.parse_id) then existence in `verses`. Returns verse_id or raises."""
    if parse_id(verse_id) is None:
        raise VerseNotFound(
            f"'{verse_id}' is not a valid verse id "
            "(expected OSIS-style 'Book.Chapter.Verse', e.g. 'John.3.16' or '1Cor.5.7')."
        )
    if con.execute("SELECT 1 FROM verses WHERE verse_id=?", (verse_id,)).fetchone() is None:
        raise VerseNotFound(f"'{verse_id}' is well-formed but not present in the dataset's canonical verses.")
    return verse_id


def get_verse(con, verse_id):
    """Tier 1 (fact). The verse's canonical address, WEB text, and book metadata."""
    _resolve_verse(con, verse_id)
    r = con.execute(
        "SELECT v.verse_id, v.book, b.name AS book_name, v.chapter, v.verse, t.text, t.translation "
        "FROM verses v JOIN books b ON b.book=v.book "
        "JOIN texts t ON t.verse_id=v.verse_id "
        "WHERE v.verse_id=? AND t.translation='WEB'",
        (verse_id,),
    ).fetchone()
    return {
        "verse_id": r["verse_id"],
        "book": r["book"],
        "book_name": r["book_name"],
        "chapter": r["chapter"],
        "verse": r["verse"],
        "text": r["text"],
        "translation": r["translation"],
    }


def cross_references(con, verse_id, min_weight=0, limit=20, include_unresolved=False, type=None, source=None):
    """Tier 2 (sourced). Verses that `verse_id` cites/points to, ordered by weight desc.

    Each item is *attributed, not asserted*: it carries source + weight + review_status. Defaults to
    resolved ('ok') edges only; `type`/`source` are first-class facet filters. The target's WEB text is
    LEFT-JOINed so flagged unresolved edges still return what is known (never silently dropped).
    """
    return _edges(con, verse_id, "source_verse_id", "target_verse_id", "target_text",
                  min_weight, limit, include_unresolved, type, source)


def back_references(con, verse_id, min_weight=0, limit=20, include_unresolved=False, type=None, source=None):
    """Tier 2 (sourced). Verses that point AT `verse_id` (where it is the target), ordered by weight desc.

    Same provenance contract as cross_references: attributed, not asserted.
    """
    return _edges(con, verse_id, "target_verse_id", "source_verse_id", "source_text",
                  min_weight, limit, include_unresolved, type, source)


def _edges(con, verse_id, anchor_col, other_col, text_key,
           min_weight, limit, include_unresolved, type, source):
    _resolve_verse(con, verse_id)
    sql = [
        f"SELECT c.{other_col} AS other_id, t.text AS other_text, c.type, c.source, c.weight, c.review_status",
        f"FROM connections c LEFT JOIN texts t ON t.verse_id=c.{other_col} AND t.translation='WEB'",
        f"WHERE c.{anchor_col}=? AND c.weight>=?",
    ]
    args = [verse_id, min_weight]
    if not include_unresolved:
        sql.append("AND c.review_status='ok'")
    if type is not None:
        sql.append("AND c.type=?"); args.append(type)
    if source is not None:
        sql.append("AND c.source=?"); args.append(source)
    sql.append(f"ORDER BY c.weight DESC, c.{other_col} ASC LIMIT ?")
    args.append(limit)
    rows = con.execute(" ".join(sql), args).fetchall()
    return [
        {
            other_col: r["other_id"],
            text_key: r["other_text"],
            "type": r["type"],
            "source": r["source"],
            "weight": r["weight"],
            "review_status": r["review_status"],
        }
        for r in rows
    ]


def reconcile_reference(con, verse_id, scheme="org"):
    """Tier 1 (fact). The verse's reference under another versification `scheme` (e.g. 'org' = Hebrew).

    Pure lookup against versification_map; 'eng' is our canonical base (identity). E.g. Joel.2.32 -> org
    Joel.3.5. Raises ValueError naming the available schemes if `scheme` is absent (never fabricated).
    """
    _resolve_verse(con, verse_id)
    r = con.execute(
        "SELECT scheme, scheme_ref, status FROM versification_map WHERE verse_id=? AND scheme=?",
        (verse_id, scheme),
    ).fetchone()
    if r is None:
        have = [x["scheme"] for x in con.execute(
            "SELECT DISTINCT scheme FROM versification_map WHERE verse_id=? ORDER BY scheme", (verse_id,))]
        raise ValueError(f"scheme '{scheme}' not available for {verse_id}; present schemes: {', '.join(have) or 'none'}.")
    return {"verse_id": verse_id, "scheme": r["scheme"], "scheme_ref": r["scheme_ref"], "status": r["status"]}


def search_text(con, query, limit=20):
    """LEXICAL substring search over WEB verse text (NOT semantic / meaning-based — that would be Tier 3).

    Case-insensitive (ASCII) substring match; results in canonical order. LIKE wildcards in `query` are
    escaped so they match literally.
    """
    needle = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = con.execute(
        "SELECT t.verse_id, t.text, t.translation FROM texts t JOIN verses v ON v.verse_id=t.verse_id "
        "WHERE t.translation='WEB' AND t.text LIKE '%' || ? || '%' ESCAPE '\\' "
        "ORDER BY v.canonical_order LIMIT ?",
        (needle, limit),
    ).fetchall()
    return [{"verse_id": r["verse_id"], "text": r["text"], "translation": r["translation"]} for r in rows]


def get_path(con, from_verse_id, to_verse_id, max_hops=3, max_frontier=2000, max_visited=20000):
    """Tier 2 (sourced). Shortest sourced-edge path from one verse to another over 'ok' connections.

    Directed (source -> target). BOUNDED, best-effort: bfs stops at max_hops, or when the frontier /
    visited caps are hit, returning found=False with truncated=True rather than exhaustively searching
    the ~614k-edge graph. Each hop carries provenance (attributed, not asserted).
    """
    _resolve_verse(con, from_verse_id)
    _resolve_verse(con, to_verse_id)
    if from_verse_id == to_verse_id:
        return {"found": True, "hops": 0, "path": [], "truncated": False}
    visited = {from_verse_id}
    frontier = [(from_verse_id, [])]            # (verse_id, path of hop dicts so far)
    truncated = False
    for _ in range(max_hops):
        nxt = []
        for vid, path in frontier:
            for r in con.execute(
                "SELECT target_verse_id, type, source, weight FROM connections "
                "WHERE source_verse_id=? AND review_status='ok' ORDER BY weight DESC",
                (vid,),
            ).fetchall():
                tgt = r["target_verse_id"]
                hop = {"from": vid, "to": tgt, "type": r["type"], "source": r["source"], "weight": r["weight"]}
                if tgt == to_verse_id:
                    return {"found": True, "hops": len(path) + 1, "path": path + [hop], "truncated": False}
                if tgt in visited:
                    continue
                visited.add(tgt)
                nxt.append((tgt, path + [hop]))
                if len(visited) >= max_visited or len(nxt) >= max_frontier:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            break
        frontier = nxt
        if not frontier:
            break
    return {"found": False, "hops": None, "path": [], "truncated": truncated}
