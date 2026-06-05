"""Unit tests for the PURE compute helpers in sinew.embed — the parts with no torch/sklearn, so they
run in CI without the `[embed]` extra. The embedding itself (model.encode) and t-SNE are exercised by
running `make embed`, not here. Skips cleanly if numpy isn't installed."""
import math

import pytest

np = pytest.importorskip("numpy")
from sinew import embed  # noqa: E402  (after importorskip)


def test_scale_clamps_to_range_and_keeps_order():
    out = embed.scale([0, 1, 2, 3, 100], 10, 20)        # 100 is an outlier -> clipped at the 98th pct
    assert out.min() >= 10 - 1e-6 and out.max() <= 20 + 1e-6
    assert out[0] <= out[1] <= out[2]                   # order preserved within the bulk


def test_mean_pool_is_unit_norm_and_nan_safe():
    m = embed.mean_pool(np.array([[3.0, 0, 0], [0, 4.0, 0]]))
    assert abs(np.linalg.norm(m) - 1.0) < 1e-6
    z = embed.mean_pool(np.zeros((2, 3)))               # degenerate -> zero vector, never NaN
    assert not np.isnan(z).any() and np.linalg.norm(z) == 0


def test_quantize_int8_is_lossless_for_ranking():
    rng = np.random.default_rng(0)
    C = rng.standard_normal((40, 16)).astype(np.float32)
    C /= np.linalg.norm(C, axis=1, keepdims=True)           # unit-normalized chapter vecs
    q, scale = embed.quantize_int8(C)
    assert q.dtype == np.int8 and q.shape == C.shape and np.abs(q).max() <= 127
    deq = q.astype(np.float32) * scale
    # dequantized cosine ~ original (uniform global scale)
    cos = np.einsum("ij,ij->i", deq, C) / (np.linalg.norm(deq, axis=1) * np.linalg.norm(C, axis=1))
    assert cos.min() > 0.99
    # a uniform scale leaves the cosine *ranking* (query vs chapters) intact (up to rounding)
    qv = C[0]
    a, b = C @ qv, q.astype(np.float32) @ qv
    assert np.argmax(a) == np.argmax(b)
    assert np.corrcoef(a, b)[0, 1] > 0.999


def test_surprise_score_is_strength_times_distance():
    assert embed.surprise_score(10, 0.5) == pytest.approx(math.log1p(10) * 0.5)
    assert embed.surprise_score(100, 0.5) > embed.surprise_score(10, 0.5)   # monotonic in votes
    assert embed.surprise_score(10, 0.9) > embed.surprise_score(10, 0.5)    # monotonic in distance


def test_diversify_caps_per_node_and_respects_limit():
    out = embed.diversify([("a", "b"), ("a", "c"), ("a", "d"), ("e", "f")], cap=2, limit=10)
    assert ("a", "b") in out and ("a", "c") in out and ("e", "f") in out
    assert ("a", "d") not in out                        # the 3rd 'a' pair is dropped by the cap
    assert len(embed.diversify([(str(i), str(-i)) for i in range(20)], cap=5, limit=3)) == 3


def test_orient_puts_nt_on_the_right():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    assert np.allclose(embed.orient(x, np.array([0, 0, 1, 1])), x)     # NT already right -> unchanged
    assert np.allclose(embed.orient(x, np.array([1, 1, 0, 0])), -x)    # NT on the left -> flipped


def test_separation_z():
    x, is_nt = np.array([0.0, 0.0, 1.0, 1.0]), np.array([0, 0, 1, 1])
    assert embed.separation_z(x, is_nt) == pytest.approx(1.0 / (x.std() + 1e-9))


def test_kinship_layout_stays_in_canvas():
    nodes = [("Gen", 1), ("Exod", 1), ("Matt", 1), ("Rom", 1)]
    idx = {n: i for i, n in enumerate(nodes)}
    W = {}
    def link(a, b, w):
        W[(a, b)] = W.get((a, b), 0) + w
        W[(b, a)] = W.get((b, a), 0) + w
    link(nodes[0], nodes[1], 5)        # OT cluster
    link(nodes[2], nodes[3], 5)        # NT cluster
    link(nodes[1], nodes[2], 1)        # a thin bridge
    kpx, kpy, sep = embed.kinship_layout(W, 4, idx, np.array([0, 0, 1, 1]))
    xlo, xhi, ylo, yhi = embed.CANVAS
    assert kpx.min() >= xlo - 1e-6 and kpx.max() <= xhi + 1e-6
    assert kpy.min() >= ylo - 1e-6 and kpy.max() <= yhi + 1e-6
    assert np.isfinite(sep)


def test_chap_parser():
    assert embed._chap("Rom.5.7") == ("Rom", 5)
    assert embed._chap("1Cor.13.4") == ("1Cor", 13)
    assert embed._chap("Nope.1.1") is None and embed._chap("garbage") is None


def _unit(rows):
    a = np.array(rows, dtype=float)
    return a / np.linalg.norm(a, axis=1, keepdims=True)


def test_top_k_links_caps_sorts_and_scores():
    nodes = [("Gen", 1), ("Exod", 1), ("Matt", 1), ("Rom", 1)]
    idx = {n: i for i, n in enumerate(nodes)}
    C = _unit([[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0, 1]])
    W = {}
    def link(a, b, w):
        W[(nodes[a], nodes[b])] = W.get((nodes[a], nodes[b]), 0) + w
        W[(nodes[b], nodes[a])] = W.get((nodes[b], nodes[a]), 0) + w
    link(0, 1, 10); link(0, 2, 5); link(0, 3, 3); link(2, 3, 8)
    links = embed.top_k_links(W, idx, C, k=2)
    assert len(links) == 4                      # one row per node
    assert links[0][0][0] == 1 and links[0][0][1] == 10    # strongest neighbor (votes) first
    assert len(links[0]) == 2                   # capped at k
    assert links[0][0][2] == pytest.approx(1.0 - float(C[0] @ C[1]), abs=1e-4)   # cos_dist recorded
    assert links[0][0][2] < links[0][1][2]      # closer-in-meaning neighbor has smaller distance


def test_nearest_neighbors_excludes_self_and_orders_by_closeness():
    C = _unit([[1, 0, 0], [0.9, 0.1, 0], [0, 1, 0], [0, 0, 1]])
    near = embed.nearest_neighbors(C, n=2)
    assert len(near) == 4 and all(len(r) == 2 for r in near)
    assert 0 not in near[0]                      # self excluded
    assert near[0][0] == 1                       # Exod is closest to Gen
