"""Versification reconciliation — adopted from the Copenhagen Alliance spec, not invented.

Builds, for the eng/KJV canonical base, a map from each eng verse to its reference in another
scheme (org = Hebrew/original; lxx deferred to P1). The Copenhagen `eng.json` `mappedVerses`
encodes eng->org; we expand each LHS/RHS reference to verse lists and pair them positionally,
labelling the relationship present (renumbered) | merged | split.

Spike-proven hard cases (see tests): Joel eng 2:32 -> org 3:5, Malachi eng 4:5 -> org 3:23,
Psalm superscription +1 shifts, the chapter-boundary shifts in Genesis/Exodus/Leviticus, etc.
Everything not named in `mappedVerses` is an identity (status=present).
"""
import json
from .books import parse_cph_ref


def build_scheme_map(mapped_verses):
    """eng->target dict: {(book,chap,verse): (book,chap,verse,status)} for every *mapped* eng verse.

    status: 'present' (1:1 renumbering), 'merged' (several eng -> one target),
    'split' (one eng -> several target; eng keeps the first target verse).
    Unmapped verses are identity and are NOT included here (callers fall back to identity).
    `flagged` collects mapping entries we could not expand (e.g. multi-chapter sides) so nothing
    fails silently.
    """
    out, flagged = {}, []
    for lhs, rhs in mapped_verses.items():
        L = parse_cph_ref(lhs)
        R = parse_cph_ref(rhs)
        if not L or not R:
            if not L and not R:
                continue                      # both sides out of 66-book scope (deuterocanon)
            flagged.append((lhs, rhs, "partial-scope"))
            continue
        # guard: each side must stay within one chapter for positional expansion to be exact
        if len({(b, c) for b, c, _ in L}) > 1 or len({(b, c) for b, c, _ in R}) > 1:
            flagged.append((lhs, rhs, "multi-chapter-side"))
            continue
        if len(L) == len(R):
            for (b, c, v), (b2, c2, v2) in zip(L, R):
                out[(b, c, v)] = (b2, c2, v2, "present")
        elif len(L) > len(R):                 # merge: collapse onto the last target
            for i, (b, c, v) in enumerate(L):
                b2, c2, v2 = R[min(i, len(R) - 1)]
                out[(b, c, v)] = (b2, c2, v2, "merged")
        else:                                  # split: eng verse -> first target; extras are target-only
            for i, (b, c, v) in enumerate(L):
                b2, c2, v2 = R[i]
                out[(b, c, v)] = (b2, c2, v2, "split")
    return out, flagged


def load_eng_to_org(cph_eng_path):
    eng = json.load(open(cph_eng_path))
    return build_scheme_map(eng["mappedVerses"])


def reconcile(book, chap, verse, scheme_map):
    """Return (org_book, org_chap, org_verse, status) for an eng verse — identity if unmapped."""
    hit = scheme_map.get((book, chap, verse))
    if hit is not None:
        return hit
    return (book, chap, verse, "present")
