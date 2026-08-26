# PRD — Sinew (v1.1)

**Product:** Sinew — an open, structured, *sourced* database of the Bible and its internal connections.
**Document version:** v1.1 (post-spike revision)
**Date:** 2026-06-01
**Status:** Draft for review
**Author:** Lucas

> *"I beheld, and lo, the sinews and the flesh came up upon them... and the breath came into them, and they lived." — Ezekiel 37:8,10*
> Sinew is the connective tissue of the canon: the layer that links verse to verse with provenance, so others build on reconnected Scripture instead of loose text.

> **Changelog v1 → v1.1 (driven by data/feasibility spikes):**
> 1. **Macula does NOT provide NT→OT citation mapping** (verified — it has speaker/quotation-mark + linguistic layers only). It is removed from the v1 critical path and returns in P1+ as an original-language Tier‑1 source.
> 2. **The typed NT→OT quotation layer (old P0 #4) moves to P1** and is **built in‑house from public‑domain sources** (Turpie 1868) via a proven pipeline — *no off‑the‑shelf typed quotation dataset exists at the right granularity/license*.
> 3. The quotation pipeline (coordinate‑OCR → 2‑D spatial pairing → two‑tier validation) is **spike‑proven**: 100% precision on the auto‑confirmed tier of Turpie Table A (≥98% target met).
> 4. Versification is **adopted, not invented** (SWORD av11n + Tyndale TVTMS, KJV/KJVA pivot).
> 5. Added: reproducible build pipeline + pinned upstream versions + validation suite as P0; `verses`/`texts` schema split.

---

## 1. Problem Statement

Anyone building software on the Bible today (study apps, sermon tools, AI agents, research) lacks a clean, open, *attributable* source for Scripture's internal connections. In practice, developers feed a PDF or raw text into an AI model and pray the inferred relationships are right — which blurs fact and interpretation, misses allusions and typology, and isn't auditable.

The problem recurs: every new biblical project redoes the same foundational work (text parsing, canonical IDs, versification reconciliation, cross-reference lookup) and, worse, **derives connections from text similarity — which is itself an interpretive assumption** (similarity ≠ connection). The cost of not solving it: ecosystem fragmentation, untrustworthy results in faith products (where errors carry weight), and the impossibility of redistributing work built on copyrighted text (e.g., ESV).

## 2. Goals

1. **Be the trusted foundation:** publish a dataset any developer can use without redoing parsing, IDs, and versification — measured by adoption (downloads + dependent projects).
2. **Separate fact from interpretation, always:** 100% of connections carry type + source + weight; no un-attributed interpretive claim; every uncertain datum is explicitly flagged, never silently asserted.
3. **Be legally redistributable:** v1 entirely under permissive licenses (public-domain text + CC-BY data), so "developers can just use it" is true.
4. **Make Scripture's self-citation real and queryable.** v1 surfaces it as *sourced connection edges* (OpenBible cross-references — the quotation pairs are present, untyped). **Typed NT→OT quotations** — the material that makes the Testament dialogue explicit — are the **headline P1 deliverable**, built in-house from public domain.
5. **Reconcile versification:** unify Hebrew / LXX / KJV numbering into one canonical map — *adopting* existing open mappings (SWORD av11n, Tyndale TVTMS) rather than hand-rolling.

## 3. Non-Goals (v1)

- **Not the explorer/visual.** The telescope map (meaning terrain + kinship arcs) is a separate *demonstration* artifact, out of scope for the v1 dataset.
- **No embeddings/similarity in the core.** Semantic search and *discovery* of new connections are Tier 3 (derived, "computed, not authoritative") and ship as a P1 module — to avoid blurring fact and computation.
- **No entities/people/places (Theographic) in v1.** Deferred for scope and license (CC-BY-SA is share-alike/viral; keeping v1 in pure CC-BY/PD avoids contamination).
- **No theological claims, no interpretive typology resolution.** Typology surfaces only indirectly, through source-attributed quotations and cross-references — never asserted by the dataset.
- **No copyrighted text (ESV, NIV, etc.).** Kills redistribution. v1 uses public domain only.
- **Typed quotations are not in v1.** They are P1 (see §6, P1‑A). v1 ships the connection graph (cross-references) and the foundation; quotation *typing* follows.

## 4. Data model — the three tiers (never blurred)

Non-negotiable principle: each datum belongs to exactly one tier, and the tier is explicit.

**Tier 1 — Facts.** Verse text, canonical IDs, book metadata, original-language words/morphology (P1+). Uncontroversial, verifiable.

**Tier 2 — Sourced connections.** Every edge is `type + source + weight (+ confidence/review-status)`. The dataset **attributes, never asserts**. v1 type: `cross_reference` (OpenBible). P1 adds `quotation` (Turpie 1868) — see P1‑A.

**Tier 3 — Derived.** Computed embeddings/similarity, explicitly labeled "computed, not authoritative." Semantic search + discovery of new connections. **Out of v1** (P1 module).

## 5. User Stories (ordered by priority)

- As a **Bible-app developer**, I want one file with text + canonical IDs + cross-references, so I don't reimplement parsing and versification.
- As a **developer**, I want every connection to carry type, source, and weight (and, when uncertain, an explicit review flag), so I can show provenance and decide what to trust.
- As an **AI-agent builder**, I want to query connections through grounded tools (MCP), so the agent cites real edges instead of hallucinating.
- As an **international developer**, I want the verse address stable across translations and numbering schemes, so I can align Hebrew/LXX/KJV without breaking references.
- As a **researcher**, I want the typed NT→OT quotation list with its source (Turpie 1868) **and** its textual-relationship class (agrees with Hebrew & LXX, differs, etc.), so I can study how the NT uses the OT — including LXX-following quotations.
- *(Edge)* As a **developer**, when a verse doesn't exist in a given numbering scheme, I want an explicit mapping rather than a silent error.

## 6. Requirements

### Must-Have (P0) — the dataset doesn't ship without these

1. **Public-domain text, keyed by canonical ID.** ≥1 PD English translation (WEB recommended; KJV/ASV optional). Source: scrollmapper/bible_databases.
   - *Acceptance:* given a canonical ID, return exact text; every canonical verse has an ID; ID↔text round-trips.
2. **Canonical ID scheme + versification reconciliation — adopted, not invented (SPIKE-PROVEN).** Canonical base = **"org"** (Hebrew/original; matches Macula). Adopt the **Copenhagen Alliance versification mappings** (open-license JSON: `eng.json`, `lxx.json`, `vul.json`, … → org), with **Tyndale TVTMS** (CC-BY) as a scholarly cross-check. OpenBible (English/KJV) maps in via `eng→org`.
   - *Spike result (2026-06-01):* a reconciler built on Copenhagen `eng.json`/`lxx.json` resolved **every** hard case correctly — Joel (eng 2:32 → org 3:5, identical to Hebrew 3:5), Malachi (eng 4:5 → org 3:23), Psalm superscriptions (67 mappings), the full LXX Psalm offset (145 mappings); non-divergent verses pass through unchanged. The only unparsed entries are **deuterocanonical** (out of Protestant v1 scope) — for the 66-book canon the mapping is **complete**.
   - *Acceptance:* known divergences (Psalm titles, Joel/Malachi shifts, split/merged verses) map correctly; verses absent in a scheme are explicitly flagged, not omitted.
   - *Confirm-in-build (low risk):* verify OpenBible uses English/KJV versification (TSK-based — high confidence).
3. **Cross-references as Tier 2 edges.** Import OpenBible (~340k) with `type=cross_reference`, `source=OpenBible`, `weight=votes`.
   - *Acceptance:* every edge has source/target/type/source-attribution/weight; **endpoints are remapped to canonical IDs via the versification map, and edges whose endpoints don't resolve are flagged, not dropped**; weights preserved.
4. **Reproducible build pipeline + provenance.** Open ETL repo that regenerates the dataset from raw sources, with **pinned upstream versions/commits** recorded in the dataset metadata.
   - *Acceptance:* `make build` (or equiv.) reproduces the published artifact byte-for-byte from pinned inputs.
5. **Validation suite (CI).** Every edge endpoint resolves to a real canonical ID; every canonical verse has ≥1 text; versification divergence fixtures pass; **no silent failures**.
6. **Distribution as a static dataset (source of truth).** SQLite file + Parquet on HuggingFace, single clear permissive license (**CC-BY, carrying required attribution to OpenBible**; PD text is unrestricted).
   - *Acceptance:* single download; documented schema; querying a verse's neighbors works offline with no proprietary dependencies.
7. **Documented schema + data contract.** README with data dictionary, tier of each field, dataset versioning, and source attributions.

### Nice-to-Have (P1) — fast-follow

**P1‑A — Typed NT→OT quotation layer (the headline differentiator).** Built in-house from public domain (see §7‑bis for the proven method).
- *Source:* **Turpie 1868, *The Old Testament in the New*** (archive.org `oldtestamentinne00turp`, public domain) — a systematic tabulation of every OT quotation in the NT, pre-classified into five textual-relationship classes (A–E).
- *Edges:* `type=quotation`, `source=Turpie1868`, plus a `turpie_class` attribute (A–E) and a `review_status` (`confirmed` | `review`).
- *Independent cross-source:* a reproducible **Swete LXX (PD) ↔ Nestle 1904 / WH 1881 GNT (PD)** verbatim/lemma matcher, providing computed direct-quotation edges (`source=computed:LXX↔GNT`) that **agree-or-flag** against Turpie.
- *Acceptance:* **confirmed-tier precision ≥98%** on a hand-keyed gold sample; 0 silent errors; every `review` edge carries a reason code; coverage and tier counts reported per table.
- *Caveat (explicit):* Turpie = **quotations** only. Allusions/echoes remain in the untyped `cross_reference` layer until a second PD source is added.

- **MCP layer** over the dataset: `get_verse`, `get_cross_references`, `get_quotations`, `reconcile_reference`. (Distribution headline — agents query grounded tools.)
- **Tier 3 — embeddings/similarity** as a separate, clearly labeled module (semantic search + discovery).
- **Original-language Tier 1 (Macula, CC-BY):** lemma/Strong's/morphology + MARBLE semantic domains. *(This is Macula's actual role — not quotations.)*
- **Thin pip/npm wrappers**; **multiple PD translations** + multilingual alignment (Portuguese) on the same verse address.

### Future Considerations (P2)

- **Entities/people/places/periods** (Theographic, CC-BY-SA) as a *separate* module (isolate share-alike from the CC-BY core).
- **The telescope visual** (meaning terrain + kinship arcs; aggregate to ~66 book-nodes, explode down).
- **Additional edge types** (`parallel`, `shares_entity`); **allusion** typing from a second PD source.
- **GraphML/edge-list** export.

## 7. Dataset contract (schema sketch)

> **Change from v1:** split translation-independent identity (`verses`) from text (`texts`) so connections reference a stable *address*, not a translation-specific row.

- `verses` — `verse_id (PK)`, `book`, `chapter`, `verse`, `canonical_order`, `tier=1`  *(translation-independent address)*
- `texts` — `verse_id (FK)`, `translation`, `text`, `tier=1`  *(PK = verse_id+translation)*
- `versification_map` — `verse_id`, `scheme (hebrew|lxx|kjv)`, `scheme_ref`, `status (present|absent|merged|split)`, `tier=1`
- `connections` — `source_verse_id`, `target_verse_id`, `type (cross_reference|quotation)`, `source`, `weight`, `confidence`, `review_status`, `turpie_class (A–E, nullable)`, `tier=2`
- `original_language` *(P1+)* — `verse_id`, `lemma`, `strongs`, `morphology`, `language`, `tier=1`
- `derived_*` *(Tier 3, P1)* — embeddings/similarity, **never** joined into fact tables.

**Schema rules:** no `connections` row without `source`; `connections.source/target` reference the canonical **address** (`verses.verse_id`), never a `texts` row; derived data lives only in `derived_*`.

## 7-bis. Proven method — the P1‑A quotation pipeline (spike-validated)

1. **Input:** Turpie's archive.org **coordinate OCR** (`*_djvu.xml`, word-level x/y boxes) — *not* the linearized text.
2. **Reference detection (anchored):** a reference counts only when it **begins a line** → prose/critical-note refs (mid-sentence) are excluded at the root.
3. **2‑D spatial pairing:** each OT ref is paired to the **nearest NT ref by vertical distance**, within a cutoff; OT refs beyond the cutoff are **orphans → flagged**, never mis-attached. (This eliminates the cascade where a missed header glues sources onto the wrong verse.)
4. **Normalization:** book-name → OSIS, Roman→Arabic (with Greek-glyph cleanup), verse-range expansion, numbered-book handling.
5. **Two-tier validation:**
   - **Verse-level bounds** (real per-chapter verse counts from the PD text) — catches `John.10.84`-type verse-OCR errors.
   - **Chapter cross-check** vs an independent reference list (mb-soft, *used as a build-time validation fixture only — not redistributed*) with LXX↔Hebrew numbering tolerance — catches `Exod.32`-vs-`33` chapter slips.
   - **Agreement** with the Swete↔GNT computational matcher.
   - → **`confirmed`** (passes checks; auto-trustworthy) vs **`review`** (flagged with a reason).
6. **Measured result (Table A):** confirmed tier **100% precise**, ~85→90%+ coverage; all OCR errors quarantined into `review`; zero silent errors.

## 8. Sources and licenses

| Source | What it provides | License | Tier / Phase |
|---|---|---|---|
| scrollmapper/bible_databases | PD translations + IDs | Public domain | 1 / P0 |
| Copenhagen Alliance versification (+ Tyndale TVTMS) | Versification mapping eng/lxx/… ↔ org | Open / CC-BY | 1 / P0 |
| OpenBible cross-references | ~340k weighted edges (built on PD TSK) | CC-BY | 2 / P0 |
| **Turpie 1868** | NT→OT quotations, classified A–E | **Public domain** | 2 / **P1‑A** |
| Swete LXX (PD) + Nestle 1904 / WH 1881 GNT (PD) | Computational quotation cross-source | Public domain | 2 / P1‑A |
| mb-soft / balinjdl OT-NT map | **Validation fixture only — NOT redistributed** | (permission-only; fixture use) | — / P1‑A |
| Macula Greek/Hebrew (Clear-Bible) | Original language + morphology + MARBLE | CC-BY | 1 / P1 |
| Theographic *(P2)* | People/places/periods | CC-BY-SA | separate module |

**Result:** the v1 + P1‑A core is entirely **CC-BY / public domain — frictionlessly redistributable** (compilation is CC-BY with attribution to OpenBible; all text/quotation inputs are PD). mb-soft is *fixture-only* and never shipped. Theographic isolated (share-alike).

## 9. Success Metrics

**Leading (weeks):** HF downloads (target 500/30d; stretch 1,500); MCP installs (P1); stars/forks.
**Lagging (months):** **public dependent projects** (target 5 in 90d — the headline "became substrate" indicator); external issues/PRs; **zero unresolved license/provenance issues filed** (signal that tier separation worked).
**Quality:** confirmed-tier quotation precision ≥98% on the gold sample; 100% of connections carry source + tier.

## 10. Open Questions

- **(Resolved)** ~~Does Macula cover NT→OT quotations?~~ **No** — verified. We build our own from Turpie 1868 (PD). 
- **(Resolved)** ~~CC-BY + PD compatibility in one file?~~ **Yes** — compilation ships CC-BY with required attribution to OpenBible; PD inputs unrestricted; mb-soft kept fixture-only.
- **(Resolved — spike 2026-06-01)** ~~Do the mappings reconcile the hard divergence cases cleanly?~~ **Yes.** The Copenhagen Alliance JSON maps resolve every protocanonical hard case (Joel, Malachi, Psalm titles, LXX Psalm offset); only deuterocanon (out of v1 scope) needs extra parsing. Adopt, don't invent. Remaining: confirm OpenBible's scheme is English/KJV (low risk).
- **(Eng, P1‑A)** Does the 2‑D pipeline generalize to the messier tables (C/D/E), or is Table A unrepresentatively clean? *(Recommend a spike.)*
- **(Product)** Trust embeddings (P1/Tier 3) for typology, or require typology to derive from a Tier 2 source? **Recommendation: the latter** (preserve "no assumptions").

## 11. Timeline / phasing

- **Phase 0 — Foundation (P0 #1, #2, #4, #5):** PD text + IDs + versification (SWORD/TVTMS) + reproducible pipeline + validation suite. The engineering bottleneck.
- **Phase 1 — Connections (P0 #3):** import OpenBible as Tier 2 cross-reference edges (remapped + flagged).
- **Phase 2 — Packaging (P0 #6, #7):** SQLite + Parquet on HF, schema docs, license. **→ v1 ship milestone.**
- **Phase 3 — Quotation layer (P1‑A):** Turpie 2‑D extractor + two-tier validation + Swete↔GNT cross-source (~1.5–2 weeks, spike-proven method).
- **Phase 4 — Distribution (P1):** MCP layer + wrappers.
- **Phase 5 — Tier 3 (P1):** embeddings module, labeled derived.

Suggestion: ship Phase 2 as a minimal public release before investing in P1, to validate adoption early.

## 12. Recommended next spikes (before/early in the build)

1. ~~**Versification reconciliation.**~~ ✅ **DONE (2026-06-01).** Copenhagen Alliance JSON maps reconcile every protocanonical hard case to an org canonical base; adopt, don't invent. P0 bottleneck retired.
2. ~~**2‑D extractor on a harder Turpie table.**~~ ✅ **DONE (2026-06-01).** Ran on Tables C & E. Extractor generalizes — Table E lands at **82%** confirmed (vs A's 85%), all correct. Table C ("NT follows LXX") is a special case: Turpie lists dual LXX+Hebrew numbering per quote, so candidate edges inflate and only the Hebrew-numbered half auto-confirms (19%); its confirmed edges are correct, and the review tier needs the Copenhagen **LXX→org normalization** (already in hand) to confirm. Real per-chapter verse bounds (Copenhagen `org.json`) composed in and fixed a range blow-up.
3. ~~**MCP-over-SQLite proof.**~~ ✅ **DONE (2026-06-01).** Built `sinew.db` (SQLite, Tier-2 sourced edges) + a dependency-free MCP stdio server (`get_quotations`, `get_quoted_by`). Full protocol roundtrip works; queries return **sourced** edges (`source=Turpie1868; tier=2`) and **"nothing rather than guessing"** when absent — the anti-hallucination distribution story, proven end-to-end.

> **All planning spikes complete.** P0 bottleneck (versification) and P1 differentiator (quotations) + distribution (MCP) are de-risked. Ready to begin the real build.
