---
pretty_name: "Sinew — sourced Bible connection-graph"
license: cc-by-4.0
language:
  - en
  - pt
tags:
  - bible
  - cross-references
  - knowledge-graph
  - versification
  - openbible
size_categories:
  - 100K<n<1M
configs:
  - config_name: connections
    data_files: parquet/connections.parquet
    default: true
  - config_name: verses
    data_files: parquet/verses.parquet
  - config_name: texts
    data_files: parquet/texts.parquet
  - config_name: books
    data_files: parquet/books.parquet
  - config_name: versification_map
    data_files: parquet/versification_map.parquet
  - config_name: dataset_meta
    data_files: parquet/dataset_meta.parquet
---

# Sinew — a *sourced* Bible connection-graph

**An open database of the Bible and its internal connections** — text + canonical IDs +
versification reconciliation + cross-references in one queryable artifact, **every connection
carrying its provenance**.

> *"…the sinews and the flesh came up upon them… and they lived." — Ezekiel 37:8,10*
> Sinew is the connective tissue of the canon — the layer that links verse↔verse *with provenance*,
> so others build on reconnected Scripture instead of feeding a PDF to an AI.

🧑‍💻 **Code, build & MCP server:** <https://github.com/LucasGalhardoLima/sinew>
🔭 **Live explorer (navigate by meaning, or search a theme):** <https://huggingface.co/spaces/LucasGalhardoLima/sinew-explorer>

[![Sinew explorer demo](https://raw.githubusercontent.com/LucasGalhardoLima/sinew/main/docs/demo.gif)](https://huggingface.co/spaces/LucasGalhardoLima/sinew-explorer)

## Why

Anyone building on the Bible (study apps, sermon tools, AI agents, research) redoes the same
foundational work — parsing text, canonical IDs, versification reconciliation, cross-reference
lookup — and worse, **derives connections from text similarity, which is itself an interpretive
assumption** (similarity ≠ connection). Sinew separates **fact from interpretation**: every
connection is `type + source + weight`, the dataset *attributes, never asserts*, and nothing is
silently dropped. v1 is entirely **public-domain text + CC-BY data** → frictionlessly redistributable.

## The three tiers (never blurred)

- **Tier 1 — Facts:** verse text, canonical IDs, book metadata, versification map.
- **Tier 2 — Sourced connections:** every edge has `type + source + weight (+ review_status)`.
- **Tier 3 — Derived (optional):** computed embeddings/similarity, *"computed, not authoritative"* —
  powers the live explorer's meaning-terrain **and its in-browser theme search**; built opt-in, never
  joined to the fact tables (and not part of this published dataset, which is Tier-1/2 only).

## What's in v1

| | |
|---|---|
| **Text** | World English Bible (WEB, English, public domain) — canonical, 31,095 verses / 1,189 chapters / 66 books. Plus Bíblia Livre (BLIVRE, pt-BR, CC BY 4.0 Brasil) and Nova Bíblia de Acesso Livre (NVA, pt-BR, CC BY-SA 4.0), each ~99.9% coverage |
| **Canonical IDs** | `Book.Chapter.Verse` (e.g. `John.3.16`), **eng/KJV** numbering base |
| **Versification** | `eng` (identity) + `org` (Hebrew) per verse, via the Copenhagen Alliance spec |
| **Connections** | OpenBible cross-references → **613,998** Tier-2 edges (`type=cross_reference`, `weight=votes`) |
| **Formats** | `sinew.sqlite` (all tables + joins) **and** per-table Parquet (this dataset's viewer) |

## Files

| Path | What |
|---|---|
| `sinew.sqlite` | The whole dataset in one SQLite file — all tables, ready for joins |
| `parquet/*.parquet` | One file per table (powers the dataset viewer above) |
| `sources.lock.json` | Exact upstream retrieval URLs + sha256 pins (reproducible build) |

## Load it

**Parquet, via 🤗 `datasets`** (each table is a named config):

```python
from datasets import load_dataset

edges  = load_dataset("LucasGalhardoLima/sinew", "connections", split="train")
verses = load_dataset("LucasGalhardoLima/sinew", "verses", split="train")
texts  = load_dataset("LucasGalhardoLima/sinew", "texts", split="train")
```

**SQLite, for joins** (one file, all tables):

```python
from huggingface_hub import hf_hub_download
import sqlite3

db = hf_hub_download("LucasGalhardoLima/sinew", "sinew.sqlite", repo_type="dataset")
con = sqlite3.connect(db)

# John 3:16 and its strongest sourced cross-references (with provenance)
con.execute("SELECT text FROM texts WHERE verse_id='John.3.16' AND translation='WEB'").fetchone()
con.execute("""SELECT target_verse_id, source, weight FROM connections
               WHERE source_verse_id='John.3.16' AND review_status='ok'
               ORDER BY weight DESC LIMIT 5""").fetchall()

# Hebrew (org) numbering for an eng verse
con.execute("SELECT scheme_ref FROM versification_map WHERE verse_id='Joel.2.32' AND scheme='org'").fetchone()
# -> ('Joel.3.5',)
```

## Schema (tables)

- **`verses`** — `verse_id (PK)`, `book`, `chapter`, `verse`, `canonical_order`, `tier=1` *(stable, translation-independent address)*
- **`books`** — `book (PK)`, `name`, `testament`, `book_number`, `chapter_count`
- **`texts`** — `verse_id`, `translation`, `text`, `tier=1` *(PK `verse_id+translation`; `WEB`, `BLIVRE`, or `NVA`)*
- **`versification_map`** — `verse_id`, `scheme ∈ {eng,org}`, `scheme_ref`, `status ∈ {present,merged,split}`, `tier=1`
- **`connections`** — `source_verse_id`, `target_verse_id`, `type`, `source`, `weight`, `confidence`, `review_status`, `turpie_class (NULL in v1)`, `tier=2`
- **`dataset_meta`** — `key`, `value`

**Rules:** no `connections` row without `source`; endpoints reference the canonical **address**
(`verses.verse_id`), never a `texts` row; an edge whose endpoint doesn't resolve (≈311, versification
gaps) is **flagged in `review_status`, never dropped** — the "no silent failure" guarantee.

## Sources & license

| Source | Provides | License |
|---|---|---|
| [World English Bible](https://ebible.org/web/) (via getbible.net v2) | PD English text (canonical) | Public Domain |
| [Bíblia Livre (BLIVRE)](https://github.com/blivre/BibliaLivre), N4 edition | pt-BR text, second `texts` translation | **CC BY 4.0 Brasil** |
| [Nova Bíblia de Acesso Livre (NVA)](https://www.biblianva.com.br/) | pt-BR text, third `texts` translation | **CC BY-SA 4.0** |
| [Copenhagen Alliance versification](https://github.com/Copenhagen-Alliance/versification-specification) | eng/org mappings | CC-BY / open |
| [OpenBible.info cross-references](https://www.openbible.info/labs/cross-references/) | ~340k weighted edges | **CC-BY** |

**This compilation is licensed CC-BY-4.0** and **requires attribution to OpenBible.info, BLIVRE,
and NVA** (see `LICENSE`); the WEB text is public domain, the BLIVRE text is CC BY 4.0 Brasil, the
NVA text is CC BY-SA 4.0 (ShareAlike binds only the NVA text itself, not the whole compilation —
see `LICENSE` for the reasoning). Exact retrieval URLs + sha256 pins are in
`sources.lock.json` and the `dataset_meta` table.

**Roadmap (P1):** typed NT→OT quotations (Turpie 1868, classified A–E); deeper Tier-3 semantic search
beyond the explorer (a query/MCP-layer semantic endpoint — the explorer's in-browser theme search
already ships); original-language (Macula) lemma/morphology; more translations + multilingual alignment beyond BLIVRE/NVA (pt-BR, shipped).
