"""Tier-3 (computed, not authoritative) meaning layer — data for the meaning-terrain explorer.

OPT-IN: needs the ``[embed]`` extra (sentence-transformers, scikit-learn, numpy). Reads the
*shipped* dataset (``dist/sinew.sqlite``: WEB ``texts`` + ``ok`` Tier-2 ``connections``) and writes:

    src/sinew/viz/data/meaning.json   committed (~hundreds of KB) -> the front-end (& `make viz`) needs no torch
    derived_* tables in dist/sinew.sqlite   (derived_meta / _chapter_layout / _chapter_vec / _surprising)

POSITIONS (and each chapter's nearest meaning-neighbors) are computed text-meaning (Tier 3,
all-mpnet-base-v2); LINKS are Tier-2 sourced OpenBible cross-references. The view is calm by default and
reveals a chapter's links only on select — a link that spans a wide meaning gap is *surprising* (a
sourced connection that is right yet non-obvious), coloured gold. Sinew never *asserts* a link
(attribute-never-assert): a long link is surfaced, not claimed.

Embeddings/t-SNE are not byte-stable across torch builds, so meaning.json is the source of truth
(model id pinned, random_state=0) and is NOT part of the core dataset's byte-for-byte claim.

Run: ``make embed`` (or ``python -m sinew.embed``) AFTER ``make build``.
"""
import json
import sqlite3
import datetime
import pathlib
from collections import defaultdict

import numpy as np

from . import query
from .books import BOOK_NUM, NT, SECTIONS, section, section_color

MODEL = "all-mpnet-base-v2"
DIM = 768
VEC_FILE = "chapter_vecs.i8.bin"        # int8 chapter vectors (node order) for in-browser theme search
CANVAS = (60, 1140, 60, 740)            # x_lo, x_hi, y_lo, y_hi (viewBox 1200x760, landscape terrain)
LINKS_K = 20                            # per chapter: top-K sourced cross-ref neighbors revealed on select
NEAR_N = 6                              # per chapter: nearest meaning-neighbors (Tier-3 on-select hint)

ROOT = pathlib.Path(__file__).resolve().parents[2]
VIZ_DATA = pathlib.Path(__file__).resolve().parent / "viz" / "data"
NODE_FIELDS = ["meaning_x", "meaning_y", "kinship_x", "kinship_y", "color", "label", "radius", "section"]
LINK_FIELDS = ["j", "votes", "cos_dist"]    # links[i] = chapter i's sourced cross-ref neighbors


# ---------------------------------------------------------------------------
# Pure helpers (no torch / no sklearn) — unit-tested directly in tests/test_embed.py
# ---------------------------------------------------------------------------
def scale(v, lo, hi):
    """Map values into [lo, hi], robust to outliers by clipping to the 2nd/98th percentile."""
    v = np.asarray(v, dtype=float)
    a, b = np.percentile(v, 2), np.percentile(v, 98)
    v = np.clip(v, a, b)
    return lo + (v - a) / (b - a + 1e-9) * (hi - lo)


def mean_pool(vecs):
    """A chapter vector = L2-normalized mean of its verse vectors (embed short verses, not long chapters)."""
    m = np.asarray(vecs, dtype=float).mean(0)
    n = np.linalg.norm(m)
    return m / n if n > 0 else m


def surprise_score(votes, cos_dist):
    """A sourced edge is 'surprising' when strongly attested (votes) yet spans a wide meaning gap."""
    return float(np.log1p(votes) * cos_dist)


def quantize_int8(C):
    """Quantize L2-normalized chapter vectors to int8 with ONE global scale. A uniform scale leaves the
    cosine *ranking* of chapters (for any query) exact up to rounding, so the explorer can rank by a
    plain int8 dot product. Returns (q [n,dim] int8, scale) with unit_component ≈ q * scale."""
    C = np.asarray(C, dtype=np.float32)
    maxabs = float(np.max(np.abs(C))) or 1.0
    q = np.clip(np.round(C / maxabs * 127.0), -127, 127).astype(np.int8)
    return q, maxabs / 127.0


def diversify(ranked, cap=2, limit=150):
    """Keep top-ranked (a, b, ...) rows while capping how often any node repeats, so a few hub nodes
    don't saturate the surfaced set. ``a``/``b`` (rows[0], rows[1]) must be hashable."""
    used, out = defaultdict(int), []
    for row in ranked:
        a, b = row[0], row[1]
        if used[a] >= cap or used[b] >= cap:
            continue
        out.append(row)
        used[a] += 1
        used[b] += 1
        if len(out) >= limit:
            break
    return out


def orient(x, is_nt):
    """Flip the x-axis so the NT centroid sits to the right (the axes are otherwise arbitrary)."""
    x = np.asarray(x, dtype=float)
    is_nt = np.asarray(is_nt)
    return -x if x[is_nt == 1].mean() < x[is_nt == 0].mean() else x


def separation_z(x, is_nt):
    """|mean_NT - mean_OT| / std on an axis — how strongly it separates the Testaments."""
    x = np.asarray(x, dtype=float)
    is_nt = np.asarray(is_nt)
    return float(abs(x[is_nt == 1].mean() - x[is_nt == 0].mean()) / (x.std() + 1e-9))


def _chap(vid):
    """('Rom', 5) from 'Rom.5.7' (single ids only — connections stores expanded verses). None if bad."""
    p = vid.split(".")
    if len(p) < 2 or p[0] not in BOOK_NUM:
        return None
    try:
        return (p[0], int(p[1]))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------
def meaning_layout(C, is_nt):
    """t-SNE(cosine) of chapter vectors -> the meaning terrain. NT oriented right, scaled to canvas."""
    from sklearn.manifold import TSNE
    xy = TSNE(n_components=2, metric="cosine", init="pca", perplexity=30,
              learning_rate="auto", random_state=0).fit_transform(C)
    x = orient(xy[:, 0], is_nt)
    xlo, xhi, ylo, yhi = CANVAS
    return scale(x, xlo, xhi), scale(xy[:, 1], ylo, yhi), separation_z(x, is_nt)


def kinship_layout(W, n, idx, is_nt):
    """Normalized-Laplacian spectral embedding of the weighted cross-ref graph -> oriented, scaled 2-D."""
    A = np.zeros((n, n))
    for (a, b), w in W.items():
        A[idx[a], idx[b]] = np.log1p(w)
    A = (A + A.T) / 2
    d = A.sum(1)
    d[d <= 0] = 1e-9
    Dinv = 1 / np.sqrt(d)
    L = np.eye(n) - Dinv[:, None] * A * Dinv[None, :]
    _vals, vecs = np.linalg.eigh(L)
    emb = vecs[:, 1:6] * Dinv[:, None]          # skip the trivial first eigenvector
    seps = sorted(((separation_z(emb[:, k], is_nt), k) for k in range(emb.shape[1])), reverse=True)
    ax, ay = seps[0][1], seps[1][1]             # the two most Testament-separating axes
    x = orient(emb[:, ax], is_nt)
    xlo, xhi, ylo, yhi = CANVAS
    return scale(x, xlo, xhi), scale(emb[:, ay], ylo, yhi), separation_z(x, is_nt)


# ---------------------------------------------------------------------------
# Read the shipped dataset
# ---------------------------------------------------------------------------
def load_verses(con):
    """WEB verse text in canonical order. Returns (verse_ids, texts)."""
    rows = con.execute(
        "SELECT t.verse_id, t.text FROM texts t JOIN verses v ON v.verse_id=t.verse_id "
        "WHERE t.translation='WEB' ORDER BY v.canonical_order"
    ).fetchall()
    return [r["verse_id"] for r in rows], [r["text"] for r in rows]


def chapter_nodes(verse_ids):
    """Ordered unique (book, chapter) by (book_number, chapter) + the verse-row indices per chapter."""
    rows_by_chap = defaultdict(list)
    for i, vid in enumerate(verse_ids):
        b, c, _ = vid.split(".")
        rows_by_chap[(b, int(c))].append(i)
    nodes = sorted(rows_by_chap, key=lambda bc: (BOOK_NUM[bc[0]], bc[1]))
    return nodes, rows_by_chap


def scan_connections(con, idx, vid_set):
    """One pass over `ok` Tier-2 edges -> (W, pv).

    W:  summed-weight undirected CHAPTER adjacency (off-map / intra-chapter skipped).
    pv: max weight per unordered cross-chapter VERSE pair (both endpoints present) — the surprise drill.
    """
    W = defaultdict(float)
    pv = {}
    for r in con.execute(
        "SELECT source_verse_id, target_verse_id, weight FROM connections WHERE review_status='ok'"
    ):
        s, t, w = r["source_verse_id"], r["target_verse_id"], max(r["weight"] or 0, 1)
        ca, cb = _chap(s), _chap(t)
        if ca and cb and ca != cb and ca in idx and cb in idx:
            W[(ca, cb)] += w
            W[(cb, ca)] += w
            if s in vid_set and t in vid_set:
                key = (s, t) if s < t else (t, s)
                if w > pv.get(key, 0):
                    pv[key] = w
    return W, pv


# ---------------------------------------------------------------------------
# Surprising connections
# ---------------------------------------------------------------------------
def top_k_links(W, idx, C, k=LINKS_K):
    """Per chapter, its top-K *sourced* cross-ref neighbors (Tier-2), revealed on select — not a global mass.

    Returns a list aligned to node order: links[i] = [[j, votes, cos_dist], ...] sorted by votes desc, ≤k.
    `cos_dist = 1 - C[i]·C[j]` (the teal->gold surprise scale); arcs are drawn one chapter at a time, so K
    caps both clutter and JSON size."""
    n = len(idx)
    neigh = [[] for _ in range(n)]
    for (a, b), w in W.items():                      # W is symmetric; record one direction per ordered key
        neigh[idx[a]].append((idx[b], w))
    links = []
    for i in range(n):
        top = sorted(neigh[i], key=lambda jw: -jw[1])[:k]
        links.append([[j, int(w), round(1.0 - float(C[i] @ C[j]), 4)] for j, w in top])
    return links


def nearest_neighbors(C, n=NEAR_N):
    """Per chapter, its N nearest meaning-neighbors (Tier-3) by cosine — a subtle on-select halo, no arcs.

    C is L2-normalized, so C @ C.T is cosine similarity; we take the top-N excluding self."""
    sims = C @ C.T
    np.fill_diagonal(sims, -2.0)                      # exclude self
    order = np.argsort(-sims, axis=1)[:, :n]
    return [[int(j) for j in row] for row in order]


def verse_surprises(pv, V, vrow, limit=150):
    """Verse-level surprising sourced connections (diversified): (src, dst, votes, dist, score, cross)."""
    keys = list(pv.keys())
    if not keys:
        return []
    ia = np.array([vrow[a] for a, _b in keys])
    ib = np.array([vrow[b] for _a, b in keys])
    vdist = 1.0 - np.einsum("ij,ij->i", V[ia], V[ib])
    vvotes = np.array([pv[k] for k in keys], dtype=float)
    vscore = np.log1p(vvotes) * vdist

    def bk(vid):
        return vid.split(".")[0]

    ranked = []
    for r in np.argsort(-vscore):
        a, b = keys[r]
        ranked.append((a, b, int(vvotes[r]), float(vdist[r]), float(vscore[r]),
                       (bk(a) in NT) != (bk(b) in NT)))
    return diversify(ranked, cap=2, limit=limit)


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def _embed(texts):
    """The one torch-dependent step: encode every verse once (cached model, normalized 768-d)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL)
    V = model.encode(texts, batch_size=128, normalize_embeddings=True,
                     show_progress_bar=True, convert_to_numpy=True).astype(np.float32)
    assert V.shape == (len(texts), DIM) and not np.isnan(V).any(), V.shape
    return V


def write_chapter_vecs(C, out_dir):
    """Write the int8 chapter vectors (flat, row-major, node order) the explorer fetches for theme
    search, and return the meta block advertising them in meaning.json. The query is embedded in-browser
    with the *same* model (Xenova/all-mpnet-base-v2, mean-pooled + normalized) and ranked by dot product."""
    q, scale = quantize_int8(C)
    n, dim = q.shape
    (out_dir / VEC_FILE).write_bytes(q.tobytes())
    return {"file": VEC_FILE, "dtype": "int8", "n": int(n), "dim": int(dim), "scale": float(scale),
            "order": "node", "model": MODEL, "hub_id": "Xenova/all-mpnet-base-v2",
            "pool": "mean", "normalized": True}


def build_meaning_json(nodes, mpx, mpy, kpx, kpy, deg, links, near, sep_m, sep_k):
    """The committed, torch-free artifact the front-end reads (deterministic key order).

    `links`/`near` are parallel to `nodes`; arcs are drawn per-selection, never globally."""
    node_data = [
        [round(float(mpx[i]), 1), round(float(mpy[i]), 1),
         round(float(kpx[i]), 1), round(float(kpy[i]), 1),
         section_color(b), f"{b} {c}", round(2.0 + 0.8 * float(np.log1p(deg[i])), 1), section(b)]
        for i, (b, c) in enumerate(nodes)
    ]
    dmax = max((lnk[2] for row in links for lnk in row), default=1.0) or 1.0   # for teal->gold normalization
    meta = {
        "model": MODEL, "dim": DIM, "tier": 3, "k": LINKS_K, "n_near": NEAR_N,
        "layout": "tSNE(cosine,perp30) meaning; normalized-Laplacian spectral kinship",
        "score": "cos_dist = 1 - cos(meaning); gold = wide meaning gap (surprising)",
        "note": ("computed, not authoritative (Tier-3): positions + nearest-neighbors are text-meaning; "
                 "links are sourced Tier-2 cross-references. Never join to the Tier-1/2 fact tables."),
        "built_on": datetime.date.today().isoformat(),
        "n_nodes": len(nodes), "n_links": sum(len(r) for r in links), "dmax": round(dmax, 4),
        "separation_z": {"meaning": round(sep_m, 2), "kinship": round(sep_k, 2)},
        "canvas": [1200, 760],
        "node_fields": NODE_FIELDS, "link_fields": LINK_FIELDS,
        "sections": [[name, col] for name, _bs, col in SECTIONS],
    }
    return {"meta": meta, "nodes": node_data, "links": links, "near": near}


def write_derived(db_path, nodes, mpx, mpy, kpx, kpy, C, surprises):
    """Additive Tier-3 tables in sinew.sqlite (for local/power use; the viz needs only meaning.json)."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    for t in ("derived_meta", "derived_chapter_layout", "derived_chapter_vec", "derived_surprising"):
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.execute("CREATE TABLE derived_meta(model TEXT, dim INT, layout TEXT, score TEXT, "
                "built_on TEXT, note TEXT, tier INT)")
    cur.execute("CREATE TABLE derived_chapter_layout(book TEXT, chapter INT, meaning_x REAL, "
                "meaning_y REAL, kinship_x REAL, kinship_y REAL, tier INT)")
    cur.execute("CREATE TABLE derived_chapter_vec(book TEXT, chapter INT, vec BLOB, tier INT)")
    cur.execute("CREATE TABLE derived_surprising(src_verse_id TEXT, dst_verse_id TEXT, votes INT, "
                "cos_dist REAL, score REAL, cross_testament INT, tier INT)")
    cur.execute("INSERT INTO derived_meta VALUES (?,?,?,?,?,?,3)",
                (MODEL, DIM, "tSNE(cosine,perp30) meaning + spectral kinship", "log1p(votes)*cos_dist",
                 datetime.date.today().isoformat(),
                 "computed, not authoritative (Tier-3); never join to Tier-1/2 fact tables"))
    for i, (b, c) in enumerate(nodes):
        cur.execute("INSERT INTO derived_chapter_layout VALUES (?,?,?,?,?,?,3)",
                    (b, c, float(mpx[i]), float(mpy[i]), float(kpx[i]), float(kpy[i])))
        cur.execute("INSERT INTO derived_chapter_vec VALUES (?,?,?,3)",
                    (b, c, C[i].astype(np.float32).tobytes()))
    for a, b, votes, dist, score, cross in surprises:
        cur.execute("INSERT INTO derived_surprising VALUES (?,?,?,?,?,?,3)",
                    (a, b, int(votes), float(dist), float(score), int(bool(cross))))
    con.commit()
    con.close()


def build(db_path=None, out_json=None):
    """Compute the Tier-3 meaning layer and write meaning.json + derived_* tables. Returns a stats dict."""
    db_path = pathlib.Path(db_path or query.DEFAULT_DB)
    out_json = pathlib.Path(out_json) if out_json else (VIZ_DATA / "meaning.json")

    con = query.connect(db_path)
    try:
        verse_ids, texts = load_verses(con)
        nodes, rows_by_chap = chapter_nodes(verse_ids)
        idx = {n: i for i, n in enumerate(nodes)}
        W, pv = scan_connections(con, idx, set(verse_ids))
    finally:
        con.close()

    V = _embed(texts)
    vrow = {v: i for i, v in enumerate(verse_ids)}
    C = np.vstack([mean_pool(V[rows_by_chap[n]]) for n in nodes])
    is_nt = np.array([1 if b in NT else 0 for b, _c in nodes])

    mpx, mpy, sep_m = meaning_layout(C, is_nt)
    kpx, kpy, sep_k = kinship_layout(W, len(nodes), idx, is_nt)

    deg = np.zeros(len(nodes))
    for (a, _b), w in W.items():
        deg[idx[a]] += np.log1p(w)

    links = top_k_links(W, idx, C)
    near = nearest_neighbors(C)
    surprises = verse_surprises(pv, V, vrow)        # kept for the derived_surprising power-user table

    meaning = build_meaning_json(nodes, mpx, mpy, kpx, kpy, deg, links, near, sep_m, sep_k)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    meaning["meta"]["vecs"] = write_chapter_vecs(C, out_json.parent)   # int8 vectors for theme search
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(meaning, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    write_derived(db_path, nodes, mpx, mpy, kpx, kpy, C, surprises)

    return {"nodes": len(nodes), "links_total": sum(len(r) for r in links), "near_n": NEAR_N,
            "verse_surprises": len(surprises), "sep_meaning": sep_m, "sep_kinship": sep_k,
            "top_surprises": surprises[:10], "out_json": out_json}


def main():
    s = build()
    print(f"meaning layer: {s['nodes']:,} chapter nodes · {s['links_total']:,} on-demand cross-ref links "
          f"(top-{LINKS_K}/chapter) · {s['near_n']} meaning-neighbors/chapter")
    print(f"OT/NT x-separation (z):  meaning={s['sep_meaning']:.2f}   kinship={s['sep_kinship']:.2f}")
    print("  (meaning clusters by genre/theme, not Testament -> lower z is expected, and is the point)")
    print("\ntop surprising sourced connections (sourced cross-ref + wide meaning gap, diversified):")
    for a, b, votes, dist, _score, _cross in s["top_surprises"]:
        print(f"  {a:>12} <-> {b:<12}  votes={votes:>3}  dist={dist:.3f}")
    print(f"\nwrote {s['out_json'].relative_to(ROOT)}  +  derived_* tables in dist/sinew.sqlite (Tier-3)")
    print("`make viz` bundles this into the meaning view (calm by default; hover a chapter to reveal its links).")


if __name__ == "__main__":
    main()
