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

  const gArcs = mk("g"), gHalo = mk("g"), gNodes = mk("g"), gLabels = mk("g"), gFlash = mk("g");
  [gArcs, gHalo, gNodes, gLabels, gFlash].forEach(g => svg.appendChild(g));  // arcs<halo<nodes<labels<flash

  let M = null, mode = "meaning", circs = [], secLabels = [], active = -1, pinned = false;
  let labelIndex = null, maxChap = null, inputEl = null, msgEl = null;   // search / jump-to state
  let themeBtn = null, panelEl = null, embedder = null, vecs = null, themeBusy = false, lastTheme = null;

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

    // search / jump-to (chapter · verse)
    inputEl = document.getElementById("search");
    msgEl = document.getElementById("searchMsg");
    buildLabelIndex();
    inputEl.addEventListener("keydown", ev => {
      if (ev.key === "Enter") { ev.preventDefault(); ev.shiftKey ? runTheme() : runSearch(); }
      else if (ev.key === "Escape") { inputEl.value = ""; searchMsg(""); clearTheme(); pinned = false; clearReveal(); }
    });
    document.getElementById("go").addEventListener("click", runSearch);
    themeBtn = document.getElementById("theme");
    panelEl = document.getElementById("themePanel");
    themeBtn.addEventListener("click", runTheme);

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
    else if (lastTheme) applyThemeHighlight(lastTheme.order, lastTheme.sims);
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
    if (i < 0 || (pinned && i === active)) { pinned = false; clearTheme(); clearReveal(); return; }
    clearTheme(); pinned = true; drawReveal(i); placeTip(ev);
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

  // ---- search / jump-to (chapter · verse) ----
  // Resolve a free-typed reference ("Isaiah 53", "Isa 53", "Ps 23", "John 3:16", "1 Cor 13", or a bare
  // book name) to a chapter node and pin it — reusing drawReveal + the click-to-pin path. Fully
  // client-side over the labels already in meaning.json (OSIS tokens like "Isa 53"); no new data. The
  // explorer is chapter-level, so a verse resolves to its chapter (and is echoed in the status line).
  // [book, full name, ...aliases]; the OSIS token + full name are added as aliases automatically.
  const BOOKS = [
    ["Gen", "Genesis", "gn"], ["Exod", "Exodus", "ex", "exo"], ["Lev", "Leviticus", "lv", "levit"],
    ["Num", "Numbers", "nm", "nb", "numb"], ["Deut", "Deuteronomy", "dt", "deu"],
    ["Josh", "Joshua", "jsh", "jos"], ["Judg", "Judges", "jdg", "jgs", "judges"], ["Ruth", "Ruth", "rth", "ru"],
    ["1Sam", "1 Samuel", "1sa", "1sm", "1samuel"], ["2Sam", "2 Samuel", "2sa", "2sm", "2samuel"],
    ["1Kgs", "1 Kings", "1ki", "1kg", "1kings"], ["2Kgs", "2 Kings", "2ki", "2kg", "2kings"],
    ["1Chr", "1 Chronicles", "1ch", "1chron", "1chronicles"], ["2Chr", "2 Chronicles", "2ch", "2chron", "2chronicles"],
    ["Ezra", "Ezra", "ezr"], ["Neh", "Nehemiah", "ne"], ["Esth", "Esther", "est", "es"], ["Job", "Job", "jb"],
    ["Ps", "Psalms", "psalm", "psa", "pss", "psm", "pslm"], ["Prov", "Proverbs", "pr", "prv", "pro"],
    ["Eccl", "Ecclesiastes", "ec", "ecc", "eccles", "qoh"],
    ["Song", "Song of Solomon", "sos", "sng", "ss", "canticles", "songofsongs"],
    ["Isa", "Isaiah", "is", "isah"], ["Jer", "Jeremiah", "je", "jr"], ["Lam", "Lamentations", "la"],
    ["Ezek", "Ezekiel", "eze", "ezk"], ["Dan", "Daniel", "dn", "da"], ["Hos", "Hosea", "ho"],
    ["Joel", "Joel", "jl", "joe"], ["Amos", "Amos", "am"], ["Obad", "Obadiah", "ob", "oba"],
    ["Jonah", "Jonah", "jon", "jnh"], ["Mic", "Micah", "mc"], ["Nah", "Nahum", "na"], ["Hab", "Habakkuk", "hb"],
    ["Zeph", "Zephaniah", "zep", "zp"], ["Hag", "Haggai", "hg"], ["Zech", "Zechariah", "zec", "zc"],
    ["Mal", "Malachi", "ml"], ["Matt", "Matthew", "mt", "mat"], ["Mark", "Mark", "mk", "mr", "mrk"],
    ["Luke", "Luke", "lk", "lu", "luk"], ["John", "John", "jn", "jhn", "joh"], ["Acts", "Acts", "ac", "act"],
    ["Rom", "Romans", "ro", "rm"], ["1Cor", "1 Corinthians", "1co", "1corinthians"],
    ["2Cor", "2 Corinthians", "2co", "2corinthians"], ["Gal", "Galatians", "ga"], ["Eph", "Ephesians", "ephes"],
    ["Phil", "Philippians", "php", "phlp", "philip", "philippians"], ["Col", "Colossians", "coloss"],
    ["1Thess", "1 Thessalonians", "1th", "1thes", "1thessalonians"], ["2Thess", "2 Thessalonians", "2th", "2thes", "2thessalonians"],
    ["1Tim", "1 Timothy", "1ti", "1timothy"], ["2Tim", "2 Timothy", "2ti", "2timothy"], ["Titus", "Titus", "tit"],
    ["Phlm", "Philemon", "phm", "philem", "philemon"], ["Heb", "Hebrews", "he"], ["Jas", "James", "jms", "jam", "james"],
    ["1Pet", "1 Peter", "1pe", "1pt", "1peter"], ["2Pet", "2 Peter", "2pe", "2pt", "2peter"],
    ["1John", "1 John", "1jn", "1jo", "1jhn"], ["2John", "2 John", "2jn", "2jo"], ["3John", "3 John", "3jn", "3jo"],
    ["Jude", "Jude", "jud", "jd"], ["Rev", "Revelation", "re", "apoc", "apocalypse", "revelations"],
  ];

  function normBook(s) {
    return s.toLowerCase()
      .replace(/\b1st\b/g, "1").replace(/\b2nd\b/g, "2").replace(/\b3rd\b/g, "3")
      .replace(/\bfirst\b/g, "1").replace(/\bsecond\b/g, "2").replace(/\bthird\b/g, "3")
      .replace(/[^a-z0-9]/g, "");
  }

  const OSIS_ALIASES = (() => {
    const m = new Map();
    for (const [osis, full, ...al] of BOOKS) {
      m.set(normBook(osis), osis); m.set(normBook(full), osis);
      for (const a of al) m.set(normBook(a), osis);
    }
    return m;
  })();
  const FULLNAMES = BOOKS.map(b => [normBook(b[1]), b[0]]);   // for partial-typing prefix fallback

  function resolveBook(raw) {
    const n = normBook(raw);
    if (!n) return null;
    if (OSIS_ALIASES.has(n)) return OSIS_ALIASES.get(n);
    if (n.length >= 2) {                                       // unique full-name prefix, e.g. "isai" → Isaiah
      const hits = [...new Set(FULLNAMES.filter(([fn]) => fn.startsWith(n)).map(([, o]) => o))];
      if (hits.length === 1) return hits[0];
    }
    return null;
  }

  function buildLabelIndex() {
    labelIndex = new Map(); maxChap = new Map();
    M.nodes.forEach((n, i) => {
      const lbl = n[5], sp = lbl.lastIndexOf(" ");            // "Isa 53" → token "Isa", chapter 53
      labelIndex.set(lbl.toLowerCase(), i);
      const tok = lbl.slice(0, sp), c = parseInt(lbl.slice(sp + 1), 10);
      if (!maxChap.has(tok) || c > maxChap.get(tok)) maxChap.set(tok, c);
    });
  }

  function parseQuery(str) {
    const s = str.trim();
    if (!s) return null;
    let raw, chap, verse = null;
    const m = s.match(/^(.*?)[\s.]*(\d+)(?::\s*(\d+))?\s*$/);  // trailing number = chapter (leading stays in book)
    if (m && m[1].trim()) { raw = m[1]; chap = parseInt(m[2], 10); verse = m[3] ? parseInt(m[3], 10) : null; }
    else { raw = s; chap = 1; }                                // bare book name → its first chapter
    const osis = resolveBook(raw);
    if (!osis) return null;
    const i = labelIndex.get((osis + " " + chap).toLowerCase());
    if (i !== undefined) return { i, osis, chap, verse };
    return { error: `${osis} has no chapter ${chap} (1–${maxChap.get(osis) || "?"}).` };
  }

  function runSearch() {
    const q = inputEl.value;
    const res = parseQuery(q);
    if (!res) { searchMsg(`No reference matched “${q.trim()}”. Press “⌕ by meaning” to search it as a theme.`, true); return; }
    if (res.i === undefined) { searchMsg(res.error, true); return; }
    searchMsg("");
    clearTheme();
    pinned = true;
    drawReveal(res.i);
    placeTipAtNode(res.i);
    flash(res.i);
    statusEl.textContent = (res.verse ? `${res.osis} ${res.chap}:${res.verse} → ${M.nodes[res.i][5]}` : M.nodes[res.i][5])
      + " · pinned (Esc to clear)";
  }

  function searchMsg(text, warn) {
    if (!msgEl) return;
    msgEl.textContent = text || "";
    msgEl.classList.toggle("warn", !!warn);
  }

  function placeTipAtNode(i) {                                 // position the tooltip at the node (no mouse event)
    const ctm = svg.getScreenCTM(); if (!ctm) return;
    const [x, y] = coords(i), pt = svg.createSVGPoint();
    pt.x = x; pt.y = y;
    const sp = pt.matrixTransform(ctm);
    placeTip({ clientX: sp.x, clientY: sp.y });
  }

  function flash(i) {                                          // brief gold ring so the eye finds the jump target
    const [x, y] = coords(i), r0 = rad(M.nodes[i]), ring = mk("circle");
    ring.setAttribute("cx", x); ring.setAttribute("cy", y);
    ring.setAttribute("fill", "none"); ring.setAttribute("stroke", "#ffe6a7"); ring.setAttribute("stroke-width", "1.6");
    gFlash.appendChild(ring);
    const t0 = performance.now(), dur = 650;
    (function step(t) {
      const k = Math.min((t - t0) / dur, 1);
      ring.setAttribute("r", (r0 + 1 + 13 * k).toFixed(1));
      ring.setAttribute("stroke-opacity", (0.9 * (1 - k)).toFixed(2));
      if (k < 1) requestAnimationFrame(step); else gFlash.removeChild(ring);
    })(t0);
  }

  // ---- theme search (semantic; Tier-3, computed in the browser) ----
  // Embed the typed theme with the SAME model as the terrain (Xenova/all-mpnet-base-v2, mean-pooled +
  // normalized) via transformers.js, then rank chapters by dot product against the shipped int8 vectors
  // (meta.vecs; uniform scale keeps the ranking exact, cosine = dot*scale). Lazy: the model + vectors
  // load only on first use, so the calm default view stays light and vendored/offline. Served-only
  // (needs fetch) — on file:// it points you at the hosted explorer.
  const TJS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.6";
  const THEME_K = 12;

  async function ensureAssets(report) {
    const v = M.meta && M.meta.vecs;
    if (!v) { searchMsg("Theme search needs chapter vectors (rebuild with `make embed`).", true); return false; }
    if (!CAN_FETCH) { searchMsg("Theme search runs on the hosted explorer — try `make viz-serve` or the Space.", true); return false; }
    if (!vecs) {
      report("loading chapter vectors…");
      const buf = await fetch("data/" + v.file).then(r => { if (!r.ok) throw new Error("vectors " + r.status); return r.arrayBuffer(); });
      vecs = new Int8Array(buf);
      if (vecs.length !== v.n * v.dim) throw new Error("vector size mismatch");
    }
    if (!embedder) {
      report("loading the meaning model (one-time download)…");
      const { pipeline, env } = await import(TJS_URL);
      env.allowLocalModels = false;
      embedder = await pipeline("feature-extraction", v.hub_id, {
        dtype: "q8",
        progress_callback: p => {
          if (p && p.status === "progress" && /\.onnx/.test(p.file || "")) report(`downloading model… ${Math.round(p.progress || 0)}%`);
        },
      });
    }
    return true;
  }

  async function runTheme() {
    const q = inputEl.value.trim();
    if (!q) { searchMsg("Type a theme (e.g. forgiveness, covenant, exile), then press “⌕ by meaning”."); return; }
    if (themeBusy) return;
    themeBusy = true; themeBtn.disabled = true;
    try {
      if (!(await ensureAssets(searchMsg))) return;
      searchMsg("embedding…");
      const out = await embedder(q, { pooling: "mean", normalize: true });
      const qf = out.data, { n, dim, scale } = M.meta.vecs;
      const sims = new Float32Array(n);
      for (let i = 0; i < n; i++) { let s = 0; const off = i * dim; for (let d = 0; d < dim; d++) s += qf[d] * vecs[off + d]; sims[i] = s; }
      const order = Array.from(sims.keys()).sort((a, b) => sims[b] - sims[a]).slice(0, THEME_K);
      searchMsg("");
      showTheme(q, order, sims, scale);
    } catch (e) {
      searchMsg("Theme search couldn't load (needs network for the model): " + ((e && e.message) || e), true);
    } finally {
      themeBusy = false; themeBtn.disabled = false;
    }
  }

  function showTheme(q, order, sims, scale) {
    pinned = true; active = -1;                       // theme owns the canvas; block hover-clobber
    hideTip();                                        // drop any lingering single-chapter tooltip
    lastTheme = { q, order, sims, scale };
    applyThemeHighlight(order, sims);
    const rows = order.map((i, r) =>
      `<div class="hit" data-i="${i}" title="show ${esc(M.nodes[i][5])}'s cross-references">` +
      `<span class="lbl">${r + 1}. ${esc(M.nodes[i][5])}</span><span class="sc">${(sims[i] * scale).toFixed(2)}</span></div>`).join("");
    panelEl.innerHTML = `<h3>Theme · “${esc(q)}”</h3>` +
      `<p class="sub">${order.length} nearest chapters in meaning · cosine · Tier-3 <em>computed, not authoritative</em></p>${rows}`;
    panelEl.hidden = false;
    panelEl.querySelectorAll(".hit").forEach(el => el.addEventListener("click", () => {
      const i = +el.getAttribute("data-i"); clearTheme(); pinned = true; drawReveal(i); placeTipAtNode(i); flash(i);
    }));
    statusEl.textContent = `Theme: “${q}” — ${order.length} nearest in meaning (Tier-3, computed) · Esc to clear`;
  }

  function applyThemeHighlight(order, sims) {
    clear(gArcs); clear(gHalo);
    const inTop = new Set(order);
    const smin = sims[order[order.length - 1]], span = (sims[order[0]] - smin) || 1;
    circs.forEach((c, k) => {
      if (inTop.has(k)) {
        const t = (sims[k] - smin) / span;            // 0..1 within the top-K
        c.setAttribute("fill-opacity", (0.55 + 0.45 * t).toFixed(2));
        c.setAttribute("r", (rad(M.nodes[k]) + 1.5 + 3.5 * t).toFixed(1));
      } else {
        c.setAttribute("fill-opacity", "0.06");
        c.setAttribute("r", rad(M.nodes[k]).toFixed(2));
      }
    });
    order.slice(0, 5).forEach(i => {                  // gold halo on the strongest few
      const [x, y] = coords(i), h = mk("circle");
      h.setAttribute("cx", x); h.setAttribute("cy", y); h.setAttribute("r", (rad(M.nodes[i]) + 5).toFixed(1));
      h.setAttribute("fill", "none"); h.setAttribute("stroke", "#ffe6a7"); h.setAttribute("stroke-opacity", "0.6");
      gHalo.appendChild(h);
    });
  }

  function clearTheme() {
    if (!lastTheme) return;
    lastTheme = null;
    if (panelEl) panelEl.hidden = true;
    clear(gArcs); clear(gHalo);
    circs.forEach((c, k) => { c.setAttribute("fill-opacity", "0.5"); c.setAttribute("r", rad(M.nodes[k]).toFixed(2)); });
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
