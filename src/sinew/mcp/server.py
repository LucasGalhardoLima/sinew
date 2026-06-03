"""Sinew MCP server — a thin, read-only wrapper over dist/sinew.sqlite (FastMCP, stdio transport).

The dataset is the source of truth; this server only reads it (opened read-only) and makes no network
calls. Every connection returned carries its provenance (source + weight + review_status) so the calling
agent can cite it: connections are *attributed, not asserted* — `source` (e.g. 'OpenBible') says who
LISTS the link and `weight` is that source's vote count; Sinew does not claim the link is true.

Tiers: get_verse / reconcile_reference = Tier 1 (facts); get_cross_references / get_back_references /
get_path = Tier 2 (sourced edges); search_text is LEXICAL substring search (NOT semantic).

Requires the optional dependency group:  pip install -e ".[mcp]"   (or  pip install "sinew[mcp]").
Run:  sinew-mcp   (or  python -m sinew.mcp.server). Point clients at it via $SINEW_DB if the dataset
is not at ./dist/sinew.sqlite.
"""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .. import query as q

mcp = FastMCP("sinew")
_con = q.connect()   # opened read-only at startup; honors $SINEW_DB


@mcp.tool()
def get_verse(verse_id: str) -> dict:
    """Tier 1 (fact). Return a verse's canonical address, WEB text, and book metadata.

    verse_id is OSIS-style 'Book.Chapter.Verse' (e.g. 'John.3.16', '1Cor.5.7').
    """
    return q.get_verse(_con, verse_id)


@mcp.tool()
def get_cross_references(verse_id: str, min_weight: int = 0, limit: int = 20,
                         include_unresolved: bool = False,
                         type: Optional[str] = None, source: Optional[str] = None) -> list:
    """Tier 2 (sourced). Verses that `verse_id` cites/points to, ordered by weight (desc).

    Connections are ATTRIBUTED, NOT ASSERTED: each item carries source + weight + review_status
    (e.g. "OpenBible lists this with 968 votes") — cite the source, don't treat it as Sinew's claim.
    Returns resolved ('ok') edges only by default; set include_unresolved=True to include flagged
    edges. `type` and `source` filter by facet (today only type='cross_reference', source='OpenBible').
    """
    return q.cross_references(_con, verse_id, min_weight=min_weight, limit=limit,
                              include_unresolved=include_unresolved, type=type, source=source)


@mcp.tool()
def get_back_references(verse_id: str, min_weight: int = 0, limit: int = 20,
                        include_unresolved: bool = False,
                        type: Optional[str] = None, source: Optional[str] = None) -> list:
    """Tier 2 (sourced). Verses that point AT `verse_id` (where it is the target), ordered by weight (desc).

    Same provenance contract as get_cross_references: attributed, not asserted. Each item carries
    source + weight + review_status.
    """
    return q.back_references(_con, verse_id, min_weight=min_weight, limit=limit,
                             include_unresolved=include_unresolved, type=type, source=source)


@mcp.tool()
def reconcile_reference(verse_id: str, scheme: str = "org") -> dict:
    """Tier 1 (fact). The verse's reference under another versification scheme (e.g. 'org' = Hebrew).

    Pure lookup; 'eng' is Sinew's canonical base (identity). Example: Joel.2.32 -> org Joel.3.5.
    """
    return q.reconcile_reference(_con, verse_id, scheme)


@mcp.tool()
def search_text(query: str, limit: int = 20) -> list:
    """LEXICAL substring search over WEB verse text — NOT semantic / meaning-based search.

    Case-insensitive (ASCII) literal substring match; returns matching verses with their text in
    canonical order. For meaning-based discovery you would need a Tier-3 layer, which Sinew does not
    ship — so do not treat these results as conceptual matches.
    """
    return q.search_text(_con, query, limit=limit)


@mcp.tool()
def get_path(from_verse_id: str, to_verse_id: str, max_hops: int = 3) -> dict:
    """Tier 2 (sourced). Shortest sourced-edge path between two verses (directed source->target, 'ok' edges).

    BOUNDED / best-effort: for distant verses it may return found=False with truncated=True rather than
    searching the whole ~614k-edge graph. Each hop carries provenance (attributed, not asserted).
    """
    return q.get_path(_con, from_verse_id, to_verse_id, max_hops=max_hops)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
