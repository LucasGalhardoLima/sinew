"""Tier-2 connections — OpenBible cross-references imported as sourced edges.

Each edge carries type + source + weight; the `To` field's verse ranges are expanded into atomic
verse->verse edges (each keeping the row's vote weight). Endpoints are validated against the
canonical verse set; an edge whose source or target does not resolve is **flagged**
(review_status), never dropped — preserving the "no silent failure" guarantee.
"""
import re
from .books import parse_id, expand_openbible_ref

_INT = re.compile(r"-?\d+")


def load_cross_references(path, verse_set, counts):
    """Yield-free: return (edges, stats).

    edges: [(source_verse_id, target_verse_id, 'cross_reference', 'OpenBible',
             weight:int, confidence(None), review_status, turpie_class(None))]
    review_status: 'ok' | 'unresolved_source' | 'unresolved_target' | 'unresolved_both'
    """
    edges = []
    stats = {"rows": 0, "expanded": 0, "self_skipped": 0,
             "ok": 0, "unresolved": 0, "bad_rows": 0}
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("From") or not line.strip():
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            stats["bad_rows"] += 1
            continue
        src_raw, tgt_raw, votes_raw = parts[0].strip(), parts[1].strip(), parts[2]
        if parse_id(src_raw) is None:
            stats["bad_rows"] += 1
            continue
        m = _INT.search(votes_raw)
        weight = int(m.group()) if m else 0
        stats["rows"] += 1

        targets = expand_openbible_ref(tgt_raw, counts)
        if not targets:
            stats["bad_rows"] += 1
            continue
        for tgt in targets:
            stats["expanded"] += 1
            if tgt == src_raw:
                stats["self_skipped"] += 1
                continue
            src_ok = src_raw in verse_set
            tgt_ok = tgt in verse_set
            if src_ok and tgt_ok:
                rs = "ok"; stats["ok"] += 1
            else:
                rs = ("unresolved_both" if not src_ok and not tgt_ok
                      else "unresolved_source" if not src_ok else "unresolved_target")
                stats["unresolved"] += 1
            edges.append((src_raw, tgt, "cross_reference", "OpenBible",
                          weight, None, rs, None))
    return edges, stats
