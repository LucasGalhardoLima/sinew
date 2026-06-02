# Sinew — data dictionary

Canonical base: **eng/KJV** (`SINEW_CANONICAL_BASE`, default `eng`). `verse_id` format
`Book.Chapter.Verse` (book = OSIS-style abbreviation, e.g. `Gen`, `1Cor`, `Ps`, `Rev`).

## `verses` — Tier 1 (canonical address)
| column | type | notes |
|---|---|---|
| `verse_id` | TEXT PK | e.g. `John.3.16` — the stable, translation-independent address |
| `book` | TEXT | OSIS-style abbreviation |
| `chapter` | INTEGER | |
| `verse` | INTEGER | |
| `canonical_order` | INTEGER | 1..N in canonical Protestant order |
| `tier` | INTEGER | always `1` |

## `books` — Tier 1 (book metadata)
| column | type | notes |
|---|---|---|
| `book` | TEXT PK | abbreviation |
| `name` | TEXT | full name (e.g. `1 Corinthians`) |
| `testament` | TEXT | `OT` / `NT` |
| `book_number` | INTEGER | 1..66 |
| `chapter_count` | INTEGER | |

## `texts` — Tier 1 (verse text)
| column | type | notes |
|---|---|---|
| `verse_id` | TEXT | FK → `verses.verse_id` |
| `translation` | TEXT | `WEB` in v1 |
| `text` | TEXT | whitespace-normalized verse text |
| `tier` | INTEGER | `1` |
| | | PK = (`verse_id`, `translation`) |

## `versification_map` — Tier 1 (scheme reconciliation)
| column | type | notes |
|---|---|---|
| `verse_id` | TEXT | the eng-base id |
| `scheme` | TEXT | `eng` (identity) or `org` (Hebrew). `lxx` is P1. |
| `scheme_ref` | TEXT | the verse's reference in that scheme (e.g. `Joel.3.5` for `org`) |
| `status` | TEXT | `present` (1:1 renumbering) · `merged` (several eng → one) · `split` (one eng → several) |
| `tier` | INTEGER | `1` |

Two rows per verse in v1 (`eng`, `org`). To translate a reference between schemes, join on
`verse_id`. Known org-only verses (e.g. Hebrew Psalm superscriptions that occupy `org` verse 1)
are not enumerated under the eng base; the content verses carry their `+1` shift via `scheme_ref`.

## `connections` — Tier 2 (sourced edges)
| column | type | notes |
|---|---|---|
| `source_verse_id` | TEXT | FK → `verses.verse_id` |
| `target_verse_id` | TEXT | FK → `verses.verse_id` |
| `type` | TEXT | `cross_reference` (v1). `quotation` is P1. |
| `source` | TEXT | `OpenBible` (v1). Never NULL/empty. |
| `weight` | INTEGER | OpenBible vote count (may be negative = disputed) |
| `confidence` | REAL | NULL in v1 |
| `review_status` | TEXT | `ok` · `unresolved_source` · `unresolved_target` · `unresolved_both` |
| `turpie_class` | TEXT | NULL in v1 (P1 quotation class A–E) |
| `tier` | INTEGER | `2` |

Directed edges (source cites target). `To`-verse ranges from OpenBible are expanded into atomic
verse→verse edges, each carrying the row's `weight`. Edges with an endpoint absent from `verses`
keep an `unresolved_*` `review_status` (flagged, not dropped).

## `dataset_meta` — provenance
Key/value: `name`, `version`, `build_date`, `canonical_base`, `license`, `verse_count`,
`text_count`, `connection_count`, `connection_unresolved`, `versification_schemes`,
`source_pins` (per-source sha256), `attribution`.
