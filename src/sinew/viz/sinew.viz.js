/* Sinew telescope — a radial arc diagram over the book-level cross-reference aggregation.
 *
 * Data contract (all read straight from the dataset by sinew.export_viz, never invented):
 *   macro  = window.SINEW_BOOKS (inlined into index.html so the hero works from file://), else
 *            data/books.json: { meta:{facets:[{type,source}],...}, nodes:[...66 books...], edges:[...] }
 *   detail = data/book/<Book>.json  (lazy, served only): { edges:[{s,t,w,type,source}] }
 *   texts  = data/texts.json        (lazy, served only): { verse_id: "WEB text" }
 *
 * Every arc is a Tier-2 sourced edge: it carries type+source+weight and is rendered through
 * arcStyle(edge), keyed on (type|source). A future quotation type (P1) or computed derived_* layer
 * (Tier 3) is a new facet value + a new arcStyle branch — a layout extension, not a rewrite.
 */
(function () {
  "use strict";

  const SVG = d3.select("#viz");
  const VB = 920, CX = VB / 2, CY = VB / 2, R = 360, LABEL_R = R + 16;
  const CAN_FETCH = location.protocol !== "file:";   // file:// blocks fetch() of local JSON
  const statusEl = document.getElementById("status");
  const tip = document.getElementById("tooltip");
  const resetBtn = document.getElementById("reset");
  const xtToggle = document.getElementById("xtOnly");

  // ---- layers (paint order: edges under nodes under labels) ----
  const gEdges = SVG.append("g").attr("class", "edges");
  const gNodes = SVG.append("g").attr("class", "nodes");
  const gLabels = SVG.append("g").attr("class", "labels");

  let macro, nodeByBook, facetColor;
  let textsCache = null, detailMode = null;

  init();

  async function init() {
    macro = window.SINEW_BOOKS || (CAN_FETCH ? await getJSON("data/books.json") : null);
    if (!macro) { statusEl.textContent = "Could not load data/books.json."; return; }

    layoutNodes(macro.nodes);
    buildFacetScale(macro.meta);
    drawNodesAndLabels(macro.nodes);
    drawLegend(macro.meta);

    xtToggle.addEventListener("change", renderMacro);
    resetBtn.addEventListener("click", () => { detailMode = null; resetBtn.hidden = true; renderMacro(); });
    renderMacro();
  }

  // ---- geometry: 66 nodes on a ring, OT and NT grouped with a gap between Mal and Matt + at top ----
  function layoutNodes(nodes) {
    nodes.sort((a, b) => a.book_number - b.book_number);
    const GAP = 3, denom = nodes.length + 2 * GAP, u = (2 * Math.PI) / denom;
    const start = -Math.PI / 2 + (GAP / 2) * u;   // straddle the top with the wrap gap
    let acc = 0;
    nodes.forEach((n, i) => {
      n.angle = start + (acc + 0.5) * u;
      n.x = CX + R * Math.cos(n.angle);
      n.y = CY + R * Math.sin(n.angle);
      acc += 1;
      if (n.book_number === 39) acc += GAP;        // after Malachi → OT/NT separation
    });
    nodeByBook = new Map(nodes.map(n => [n.book, n]));
  }

  function buildFacetScale(meta) {
    const keys = (meta.facets || []).map(f => f.type + "|" + f.source);
    facetColor = d3.scaleOrdinal()
      .domain(keys.length ? keys : ["cross_reference|OpenBible"])
      .range(["#d9a441", "#5fa8a0", "#9b7bd0", "#c46a8a"]);   // facet 1 = gold; rest reserved
  }

  // arcStyle is the single styling hook, parameterized by facet. Tier-3 readiness lives here:
  // a future computed source (e.g. "derived_embeddings") returns dashed + a distinct hue, and the
  // legend already labels it "computed, not authoritative".
  function arcStyle(e) {
    const computed = /^derived/i.test(e.source || "");
    return {
      stroke: facetColor(e.type + "|" + e.source),
      dash: computed ? "3,3" : null,
    };
  }

  function drawNodesAndLabels(nodes) {
    gNodes.selectAll("circle").data(nodes).join("circle")
      .attr("class", "node-dot book-arc")
      .attr("cx", n => n.x).attr("cy", n => n.y).attr("r", 4.5)
      .attr("fill", n => n.testament === "OT" ? "#5c83a6" : "#c08a3e")
      .on("click", (_e, n) => drillInto(n))
      .append("title").text(n => `${n.name} — drill into ${n.book}`);

    gLabels.selectAll("text").data(nodes).join("text")
      .attr("class", n => "book-label " + n.testament.toLowerCase())
      .attr("x", n => CX + LABEL_R * Math.cos(n.angle))
      .attr("y", n => CY + LABEL_R * Math.sin(n.angle))
      .attr("text-anchor", n => Math.cos(n.angle) < -0.01 ? "end" : (Math.cos(n.angle) > 0.01 ? "start" : "middle"))
      .attr("dominant-baseline", "middle")
      .attr("transform", n => {
        const deg = n.angle * 180 / Math.PI;
        const flip = Math.cos(n.angle) < 0;
        const lx = CX + LABEL_R * Math.cos(n.angle), ly = CY + LABEL_R * Math.sin(n.angle);
        return `rotate(${flip ? deg + 180 : deg}, ${lx}, ${ly})`;
      })
      .text(n => n.book);
  }

  // ---- macro view: book-pair arcs ----
  function renderMacro() {
    detailMode = null; resetBtn.hidden = true;
    const xtOnly = xtToggle.checked;
    const edges = macro.edges.filter(e => !xtOnly || e.cross_testament);

    const wScale = d3.scaleSqrt().domain([1, d3.max(macro.edges, d => d.edge_count) || 1]).range([0.4, 7]);
    const oScale = d3.scaleSqrt().domain([1, d3.max(macro.edges, d => Math.abs(d.sum_weight)) || 1]).range([0.1, 0.6]);

    gNodes.selectAll("circle").classed("dim", false).attr("opacity", 1)
      .attr("r", 4.5)
      .attr("fill", n => n.testament === "OT" ? "#5c83a6" : "#c08a3e");
    gLabels.selectAll("text").attr("opacity", 1).attr("font-weight", null);

    gEdges.selectAll("path").data(edges, d => d.source_book + ">" + d.target_book + "|" + d.type + "|" + d.source)
      .join("path")
      .attr("class", "edge")
      .attr("d", d => arcPath(nodeByBook.get(d.source_book), nodeByBook.get(d.target_book)))
      .attr("stroke", d => arcStyle(d).stroke)
      .attr("stroke-dasharray", d => arcStyle(d).dash)
      .attr("stroke-width", d => wScale(d.edge_count))
      .attr("stroke-opacity", d => (d.cross_testament ? 1 : 0.55) * oScale(Math.abs(d.sum_weight)))
      .on("mousemove", (ev, d) => showMacroTip(ev, d))
      .on("mouseleave", hideTip);

    const totalXT = edges.filter(e => e.cross_testament).reduce((s, e) => s + e.edge_count, 0);
    const total = edges.reduce((s, e) => s + e.edge_count, 0);
    statusEl.textContent = xtOnly
      ? `${fmt(totalXT)} cross-Testament references among ${macro.nodes.length} books · ${facetLabel()}`
      : `${fmt(total)} references among ${macro.nodes.length} books · ${facetLabel()}`;
  }

  // ---- drill-down: a book's verse-level outgoing edges (top by weight, for legibility/perf) ----
  async function drillInto(node) {
    if (!CAN_FETCH) {
      statusEl.textContent = `Drill-down needs a server — run \`make viz-serve\`, then click ${node.book}.`;
      return;
    }
    statusEl.textContent = `Loading ${node.name}…`;
    try {
      const [detail] = await Promise.all([
        getJSON(`data/book/${node.book}.json`),
        textsCache ? Promise.resolve() : getJSON("data/texts.json").then(t => (textsCache = t)),
      ]);
      detailMode = node.book;
      renderDetail(node, detail);
    } catch (err) {
      statusEl.textContent = `Could not load ${node.book}.json (${err}).`;
    }
  }

  function renderDetail(node, detail) {
    resetBtn.hidden = false;
    const TOP = 400;
    const edges = detail.edges.slice().sort((a, b) => b.w - a.w).slice(0, TOP);
    const wScale = d3.scaleSqrt().domain([1, d3.max(detail.edges, d => Math.abs(d.w)) || 1]).range([0.5, 5]);

    // dim everything except the focused book and the books it reaches; make the focus the anchor
    const reached = new Set([node.book]);
    edges.forEach(e => reached.add(e.t.split(".")[0]));
    gNodes.selectAll("circle")
      .attr("opacity", n => reached.has(n.book) ? 1 : 0.16)
      .attr("r", n => n.book === node.book ? 7.5 : 4.5)
      .attr("fill", n => n.book === node.book ? "#f0d28a"
        : (n.testament === "OT" ? "#5c83a6" : "#c08a3e"));
    gLabels.selectAll("text")
      .attr("opacity", n => reached.has(n.book) ? 1 : 0.16)
      .attr("font-weight", n => n.book === node.book ? "700" : null);

    // Same geometry as the macro, isolated to one book: endpoints on the ring, default beta 0.7
    // bundling → a focused starburst. Tight jitter on the focused (source) book so its verses share a
    // clean origin; a little more on targets so sibling verses separate for hover.
    gEdges.selectAll("path").data(edges, d => d.s + ">" + d.t + "|" + d.type + "|" + d.source)
      .join("path")
      .attr("class", "edge")
      .attr("d", d => arcPath(ringPoint(d.s, 0.006), ringPoint(d.t, 0.02)))
      .attr("stroke", d => arcStyle(d).stroke)
      .attr("stroke-dasharray", d => arcStyle(d).dash)
      .attr("stroke-width", d => wScale(Math.abs(d.w)))
      .attr("stroke-opacity", 0.6)
      .on("mousemove", (ev, d) => showVerseTip(ev, d))
      .on("mouseleave", hideTip);

    statusEl.textContent = `${node.name}: top ${Math.min(TOP, detail.edges.length)} of `
      + `${fmt(detail.edges.length)} verse-level references (by weight) · hover an arc to read both verses`;
  }

  // ---- arc path: quadratic Bézier whose control point sits between the centre and the chord
  // midpoint. beta=0.7 pulls hard to the centre (the macro starburst); a low beta keeps the curve
  // near the straight chord (a clean fan, used for single-source drill-down). ----
  function arcPath(p1, p2, beta) {
    if (!p1 || !p2) return "M0,0";
    if (beta == null) beta = 0.7;
    const mx = (p1.x + p2.x) / 2, my = (p1.y + p2.y) / 2;
    const cxp = CX + (mx - CX) * (1 - beta), cyp = CY + (my - CY) * (1 - beta);
    return `M${p1.x},${p1.y}Q${cxp},${cyp} ${p2.x},${p2.y}`;
  }

  // place a verse ON the ring at its book's angle (same geometry as the macro's book nodes), plus a
  // small deterministic per-verse angular nudge (±jitter rad) so sibling verses separate for hover.
  // No radial offset — endpoints stay on the circle, which is what keeps the focused view as crisp as
  // the macro. Keep jitter well inside a book's angular slot (u = 2π/72 ≈ 0.087 rad).
  function ringPoint(vid, jitter) {
    const n = nodeByBook.get(vid.split(".")[0]);
    if (!n) return { x: CX, y: CY };
    if (jitter == null) jitter = 0.018;
    const a = n.angle + (((hashStr(vid) % 1000) / 1000) - 0.5) * 2 * jitter;
    return { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) };
  }

  // ---- tooltips ----
  function showMacroTip(ev, d) {
    const sn = nodeByBook.get(d.source_book), tn = nodeByBook.get(d.target_book);
    tip.innerHTML =
      `<div class="ref">${esc(sn.name)} → ${esc(tn.name)}</div>` +
      `<div class="txt">${fmt(d.edge_count)} cross-references` +
      (d.cross_testament ? " · crosses Testaments" : "") + `</div>` +
      `<div class="prov">${esc(d.source)} · combined weight ${fmt(d.sum_weight)} · ` +
      `Tier 2, attributed not asserted</div>`;
    placeTip(ev);
  }

  function showVerseTip(ev, d) {
    const st = (textsCache && textsCache[d.s]) || "(text unavailable)";
    const tt = (textsCache && textsCache[d.t]) || "(text unavailable)";
    tip.innerHTML =
      `<div class="ref">${esc(d.s)}</div><div class="txt">${esc(st)}</div>` +
      `<div class="ref">${esc(d.t)}</div><div class="txt">${esc(tt)}</div>` +
      `<div class="prov">${esc(d.source)}, weight ${fmt(d.w)} · Tier 2, attributed not asserted</div>`;
    placeTip(ev);
  }

  function placeTip(ev) {
    tip.hidden = false;
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > innerWidth) x = ev.clientX - w - pad;
    if (y + h > innerHeight) y = ev.clientY - h - pad;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.hidden = true; }

  // ---- legend ----
  function drawLegend(meta) {
    const el = document.getElementById("legend");
    const facets = (meta.facets || []).map(f =>
      `<div class="row"><span class="swatch" style="background:${facetColor(f.type + "|" + f.source)}"></span>` +
      `${esc(f.source)} · ${esc(f.type)}</div>`).join("");
    el.innerHTML =
      `<h3>Sourced connections (Tier 2)</h3>${facets}` +
      `<div class="note">Arc thickness = number of references; opacity = combined weight. ` +
      `Every arc is <em>attributed, not asserted</em> — the source lists it; Sinew does not claim it. ` +
      `Computed “meaning” layers (Tier 3) are not shipped; when added they appear dashed and labelled ` +
      `“computed, not authoritative.”</div>`;
  }

  // ---- helpers ----
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(r.status + " " + url);
    return r.json();
  }
  function hashStr(s) { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return Math.abs(h); }
  function fmt(n) { return (n || 0).toLocaleString("en-US"); }
  function facetLabel() { return (macro.meta.facets || []).map(f => f.source).join(", ") || "sourced"; }
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
})();
