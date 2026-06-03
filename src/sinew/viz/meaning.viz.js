/* Sinew meaning view — chapters placed by computed text-meaning (Tier 3), CALM by default.
 *
 * No arcs are drawn until you point at a chapter; then only THAT chapter's sourced cross-references
 * (Tier 2) glow — teal→gold by meaning-distance, so a "surprising" link (a sourced connection that is
 * right yet spans a wide meaning gap) reads gold — and its nearest meaning-neighbors (Tier 3) get a
 * faint halo, while everything else dims. (This mirrors how the Epicure map reveals neighbours on
 * select instead of drawing the whole graph.) Click to pin a selection; toggle the meaning⇄kinship
 * layout. Pure SVG DOM — no D3. Modeled on the chord view's dim/highlight drill (sinew.viz.js).
 *
 * Data contract (sinew.embed's meaning.json; positions/near are computed, links are sourced — never claimed):
 *   window.SINEW_MEANING (inlined into meaning.html for file://), else data/meaning.json:
 *     meta : { dmax, sections:[[name,color]], separation_z:{meaning,kinship}, n_nodes, n_links, ... }
 *     nodes: [[mx,my,kx,ky,color,label,radius,section], ...]
 *     links: [ [[j,votes,cos_dist], ...], ... ]   // parallel to nodes; chapter i's top-K sourced cross-refs
 *     near : [ [j, ...], ... ]                     // parallel to nodes; chapter i's nearest meaning-neighbors
 */
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";
  const CAN_FETCH = location.protocol !== "file:";
  const HIT = 18;                              // cursor→node pick radius, in viewBox units
  const svg = document.getElementById("viz");
  const statusEl = document.getElementById("status");
  const tip = document.getElementById("tooltip");
  const toggleBtn = document.getElementById("toggle");

  const gArcs = mk("g"), gHalo = mk("g"), gNodes = mk("g"), gLabels = mk("g");
  [gArcs, gHalo, gNodes, gLabels].forEach(g => svg.appendChild(g));   // paint order: arcs<halo<nodes<labels

  let M = null, mode = "meaning", circs = [], secLabels = [], active = -1, pinned = false;

  init();

  async function init() {
    M = window.SINEW_MEANING || (CAN_FETCH ? await getJSON("data/meaning.json") : null);
    if (!M) { statusEl.textContent = "Could not load data/meaning.json (run `make viz-serve`)."; return; }
    buildNodes();
    buildSectionLabels();
    drawLegend();
    positionAll();
    svg.addEventListener("mousemove", onMove);
    svg.addEventListener("mouseleave", () => { if (!pinned) clearReveal(); });
    svg.addEventListener("click", onClick);
    toggleBtn.addEventListener("click", () => {
      mode = mode === "meaning" ? "kinship" : "meaning";
      positionAll();
      updateStatus();
    });
    updateStatus();
  }

  function coords(i) { const n = M.nodes[i]; return mode === "meaning" ? [n[0], n[1]] : [n[2], n[3]]; }

  // ---- build (once) ----
  // gentler than the raw degree-radius: a calmer, more uniform constellation (hubs don't dominate)
  function rad(n) { return Math.max(1.3, 1.3 + 0.42 * (n[6] - 2)); }

  function buildNodes() {
    circs = M.nodes.map(n => {
      const c = mk("circle");
      c.setAttribute("class", "node");
      c.setAttribute("r", rad(n).toFixed(2));
      c.setAttribute("fill", n[4]);
      c.setAttribute("fill-opacity", "0.5");
      gNodes.appendChild(c);
      return c;
    });
  }

  function buildSectionLabels() {
    const names = [...new Set(M.nodes.map(n => n[7]).filter(Boolean))];
    secLabels = names.map(name => {
      const t = mk("text");
      t.setAttribute("class", "seclabel");
      t.setAttribute("fill", sectionColor(name));
      t.textContent = name;
      gLabels.appendChild(t);
      return { name, el: t };
    });
  }

  // ---- position (initial + on layout toggle) ----
  function positionAll() {
    M.nodes.forEach((_n, i) => { const [x, y] = coords(i); circs[i].setAttribute("cx", x); circs[i].setAttribute("cy", y); });
    secLabels.forEach(s => {
      let sx = 0, sy = 0, k = 0;
      M.nodes.forEach((n, i) => { if (n[7] === s.name) { const [x, y] = coords(i); sx += x; sy += y; k++; } });
      if (k) { s.el.setAttribute("x", (sx / k).toFixed(1)); s.el.setAttribute("y", (sy / k).toFixed(1)); }
    });
    if (active >= 0) drawReveal(active);        // keep the revealed arcs aligned after a layout swap
  }

  // ---- reveal one chapter's connections ----
  function arcColor(t) { return `rgb(${lerp(95, 255, t)},${lerp(160, 214, t)},${lerp(150, 103, t)})`; }

  function drawReveal(i) {
    clear(gArcs); clear(gHalo);
    const links = M.links[i] || [], near = M.near[i] || [];
    const bright = new Set([i]);
    links.forEach(l => bright.add(l[0]));
    near.forEach(j => bright.add(j));
    circs.forEach((c, k) => { c.setAttribute("fill-opacity", bright.has(k) ? "0.95" : "0.06"); });
    circs[i].setAttribute("r", (rad(M.nodes[i]) + 2).toFixed(1));

    // nearest meaning-neighbors (Tier-3): a faint dashed halo, no arcs
    near.forEach(j => {
      const [x, y] = coords(j), h = mk("circle");
      h.setAttribute("cx", x); h.setAttribute("cy", y); h.setAttribute("r", (rad(M.nodes[j]) + 3).toFixed(1));
      h.setAttribute("fill", "none"); h.setAttribute("stroke", "#cfd6e0");
      h.setAttribute("stroke-opacity", "0.45"); h.setAttribute("stroke-dasharray", "2,2");
      gHalo.appendChild(h);
    });

    // sourced cross-references (Tier-2): teal→gold by meaning-distance, width by votes
    const [x1, y1] = coords(i), dmax = M.meta.dmax || 1;
    const vmax = links.reduce((m, l) => Math.max(m, l[1]), 1);
    links.forEach(l => {
      const [x2, y2] = coords(l[0]), t = Math.min(l[2] / dmax, 1), p = mk("path");
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - Math.abs(x2 - x1) * 0.12;
      p.setAttribute("class", "arc");
      p.setAttribute("d", `M${x1},${y1} Q${mx.toFixed(1)},${my.toFixed(1)} ${x2},${y2}`);
      p.setAttribute("stroke", arcColor(t));
      p.setAttribute("stroke-width", (0.5 + 2.2 * Math.sqrt(l[1] / vmax)).toFixed(2));
      p.setAttribute("stroke-opacity", "0.9");
      p.setAttribute("stroke-linecap", "round");
      gArcs.appendChild(p);
    });

    active = i;
    setTip(i);
    updateStatus();
  }

  function clearReveal() {
    clear(gArcs); clear(gHalo);
    circs.forEach((c, k) => { c.setAttribute("fill-opacity", "0.5"); c.setAttribute("r", rad(M.nodes[k]).toFixed(2)); });
    active = -1; hideTip(); updateStatus();
  }

  // ---- pointer ----
  function nearestNode(ev) {
    const ctm = svg.getScreenCTM();
    if (!ctm) return -1;
    const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const loc = pt.matrixTransform(ctm.inverse());
    let best = -1, bd = HIT * HIT;
    for (let i = 0; i < M.nodes.length; i++) {
      const [x, y] = coords(i), dx = loc.x - x, dy = loc.y - y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  function onMove(ev) {
    if (pinned) return;
    const i = nearestNode(ev);
    if (i < 0) { if (active >= 0) clearReveal(); return; }
    if (i !== active) drawReveal(i);
    placeTip(ev);
  }

  function onClick(ev) {
    const i = nearestNode(ev);
    if (i < 0 || (pinned && i === active)) { pinned = false; clearReveal(); return; }
    pinned = true; drawReveal(i); placeTip(ev);
  }

  // ---- chrome ----
  function setTip(i) {
    const n = M.nodes[i], L = M.links[i] || [], nr = (M.near[i] || []).length, dmax = M.meta.dmax || 1;
    const gold = L.filter(l => l[2] / dmax > 0.66).length;
    tip.innerHTML =
      `<div class="ref">${esc(n[5])}</div>` +
      `<div class="prov">${L.length} sourced cross-reference${L.length === 1 ? "" : "s"}` +
      (gold ? ` · <span style="color:var(--gold)">${gold} surprising</span> (wide meaning gap)` : "") +
      ` · ${nr} nearest in meaning<br>links = Tier-2 sourced (attributed, not asserted) · position = Tier-3 computed</div>`;
    tip.hidden = false;
  }

  function updateStatus() {
    const sep = M.meta.separation_z || {};
    if (active < 0) {
      statusEl.textContent = "Hover any chapter to reveal its cross-references · "
        + (mode === "meaning"
          ? `meaning terrain — clusters by genre/theme (OT/NT z=${sep.meaning ?? "?"})`
          : `kinship layout — from the cross-ref graph (z=${sep.kinship ?? "?"})`);
    } else {
      statusEl.textContent = M.nodes[active][5] + (pinned ? "  ·  pinned (click empty space to release)" : "");
    }
  }

  function drawLegend() {
    const el = document.getElementById("legend");
    if (!el) return;
    const rows = (M.meta.sections || []).map(([name, col]) =>
      `<span class="row"><span class="dot" style="background:${col}"></span>${esc(name)}</span>`).join("");
    el.innerHTML =
      `<h3>${fmt(M.meta.n_nodes)} chapters · positioned by meaning</h3>${rows}` +
      `<div class="note">Position = <em>computed</em> meaning (${esc(M.meta.model || "")}, Tier 3 — not ` +
      `authoritative). Hover a chapter → its <em>sourced</em> cross-references (Tier 2); ` +
      `<span style="color:var(--gold)">gold = surprising</span> (a sourced link spanning a wide meaning ` +
      `gap). Dashed halo = nearest in meaning. Sinew attributes, it does not assert.</div>`;
  }

  // ---- helpers ----
  function mk(tag) { return document.createElementNS(SVGNS, tag); }
  function fmt(n) { return (n || 0).toLocaleString("en-US"); }
  function clear(g) { while (g.firstChild) g.removeChild(g.firstChild); }
  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
  function sectionColor(name) { const s = (M.meta.sections || []).find(x => x[0] === name); return s ? s[1] : "#9aa0ab"; }
  async function getJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status + " " + url); return r.json(); }
  function placeTip(ev) {
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = ev.clientX + pad, y = ev.clientY + pad;
    if (x + w > innerWidth) x = ev.clientX - w - pad;
    if (y + h > innerHeight) y = ev.clientY - h - pad;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.hidden = true; }
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
})();
