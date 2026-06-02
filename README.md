---
pretty_name: "Sinew — sourced Bible connection-graph"
license: cc-by-4.0
language:
  - en
tags:
  - bible
  - cross-references
  - knowledge-graph
  - versification
  - openbible
size_categories:
  - 100K<n<1M
---

# Sinew

**An open, *sourced* database of the Bible and its internal connections** — text + canonical IDs +
versification reconciliation + cross-references, in one queryable artifact, every connection
carrying its provenance.

> *"…the sinews and the flesh came up upon them… and they lived." — Ezekiel 37:8,10*
> Sinew is the connective tissue of the canon: the layer that links verse↔verse with provenance,
> so others build on reconnected Scripture instead of feeding a PDF to an AI.

## Why

Anyone building on the Bible (study apps, sermon tools, AI agents, research) re-does the same
foundational work — text parsing, canonical IDs, versification reconciliation, cross-reference
lookup — and worse, **derives connections from text similarity, which is itself an interpretive
assumption** (similarity ≠ connection). Sinew separates **fact from interpretation**: every
connection is `type + source + weight`, the dataset *attributes, never asserts*, and nothing is
silently dropped. v1 is entirely **public-domain text + CC-BY data** → frictionlessly redistributable.

## The three tiers (never blurred)

- **Tier 1 — Facts:** verse text, canonical IDs, book metadata, versification map.
- **Tier 2 — Sourced connections:** every edge has `type + source + weight (+ review_status)`.
- **Tier 3 — Derived (not in v1):** computed embeddings/similarity, *"computed, not authoritative."*

## What's in v1

| | |
|---|---|
| **Text** | World English Bible (WEB), public domain, 31,095 verses / 1,189 chapters / 66 books |
| **Canonical IDs** | `Book.Chapter.Verse` (e.g. `John.3.16`), **eng/KJV** numbering base |
| **Versification** | `eng` (identity) + `org` (Hebrew) per verse, via the Copenhagen Alliance spec |
| **Connections** | OpenBible cross-references → **613,998** Tier-2 edges (`type=cross_reference`, `weight=votes`) |
| **Distribution** | `sinew.sqlite` + Parquet, reproducible pinned build, validation suite |

**Roadmap (P1, de-risked spikes, not in v1):** typed NT→OT quotations (Turpie 1868, classified
A–E); an MCP server for grounded agent queries; Tier-3 embeddings + the "meaning terrain" map;
original-language (Macula) lemma/morphology; more PD translations + multilingual alignment.

## Schema

See [`docs/schema.md`](docs/schema.md) for the full data dictionary. Tables:

- **`verses`** — `verse_id (PK)`, `book`, `chapter`, `verse`, `canonical_order`, `tier=1` *(stable, translation-independent address)*
- **`books`** — `book (PK)`, `name`, `testament`, `book_number`, `chapter_count`
- **`texts`** — `verse_id`, `translation`, `text`, `tier=1` *(PK `verse_id+translation`; v1: WEB only)*
- **`versification_map`** — `verse_id`, `scheme ∈ {eng,org}`, `scheme_ref`, `status ∈ {present,merged,split}`, `tier=1`
- **`connections`** — `source_verse_id`, `target_verse_id`, `type`, `source`, `weight`, `confidence`, `review_status`, `turpie_class (NULL in v1)`, `tier=2`
- **`dataset_meta`** — `key`, `value` *(version, build date, source pins, license, base scheme)*

**Rules:** no `connections` row without `source`; endpoints reference the canonical **address**
(`verses.verse_id`), never a `texts` row; derived data would live only in `derived_*` tables.

### Canonical IDs & versification

`verse_id` uses **eng/KJV** numbering — what both inputs (WEB, OpenBible) use and what most
developers cite, so it is identity-mapped (fewest error sites). The Hebrew/original (`org`)
reference for every verse is one join away in `versification_map`, so nothing is lost and Hebrew
alignment (and P1 original-language) is ready. The reconciler resolves every protocanonical
divergence (verified in tests): Joel `eng 2:32 → org 3:5`, Malachi `eng 4:5 → org 3:23`, Psalm
superscription shifts (`Ps 51:1 → org 51:3`), chapter-boundary shifts, etc. *LXX numbering is a P1
addition (needed mainly by the quotation layer).*

### Connections

OpenBible cross-reference votes, imported as directed `cross_reference` edges with `weight=votes`.
`To`-verse **ranges are expanded** into atomic verse→verse edges. Endpoints are validated against
the verse set; an edge whose endpoint doesn't resolve (≈311, versification gaps) is **flagged in
`review_status` (`unresolved_*`), never dropped** — the "no silent failure" guarantee.

## Usage

```python
import sqlite3
con = sqlite3.connect("sinew.sqlite")

# text of a verse
con.execute("SELECT text FROM texts WHERE verse_id='John.3.16'").fetchone()

# its strongest cross-references (with provenance)
con.execute("""SELECT target_verse_id, source, weight FROM connections
               WHERE source_verse_id='John.3.16' AND review_status='ok'
               ORDER BY weight DESC LIMIT 5""").fetchall()

# Hebrew (org) numbering for an eng verse
con.execute("SELECT scheme_ref FROM versification_map WHERE verse_id='Joel.2.32' AND scheme='org'").fetchone()
# -> ('Joel.3.5',)
```

Parquet (`dist/parquet/*.parquet`) loads in pandas/duckdb/polars for analytics.

## Build & reproduce

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
make fetch      # verify raw inputs match the pinned sha256 in sources.lock.json
make build      # data/raw -> dist/sinew.sqlite + dist/parquet/
make validate   # P0 checks: every verse has text, endpoints resolve-or-flagged, fixtures pass
make test       # pytest
```

The build reads only the pinned `data/raw/` inputs and writes sorted rows, so it reproduces the
data byte-for-byte. `make fetch --download` re-pulls from upstream and reports any drift.

## Sources & licenses

| Source | Provides | License |
|---|---|---|
| [World English Bible](https://ebible.org/web/) (via getbible.net v2) | PD English text | Public Domain |
| [Copenhagen Alliance versification](https://github.com/Copenhagen-Alliance/versification-specification) | eng/org/lxx ↔ org mappings | CC-BY / open |
| [OpenBible.info cross-references](https://www.openbible.info/labs/cross-references/) | ~340k weighted edges | **CC-BY** |

**This compilation is licensed CC-BY-4.0** and **requires attribution to OpenBible.info**; the
underlying Bible text is public domain. Exact retrieval URLs + sha256 pins are in
[`sources.lock.json`](sources.lock.json) and `dataset_meta`.
