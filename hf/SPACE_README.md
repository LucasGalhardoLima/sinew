---
title: Sinew Explorer
emoji: 🪡
colorFrom: green
colorTo: gray
sdk: static
pinned: true
license: cc-by-4.0
short_description: Navigate the Bible by meaning; cross-references on demand
tags:
  - bible
  - knowledge-graph
  - cross-references
  - visualization
---

# Sinew Explorer

The telescope view onto **[Sinew](https://huggingface.co/datasets/LucasGalhardoLima/sinew)** — an
open, *sourced* Bible connection-graph. Two linked views:

- **Meaning view (`index.html`, hero).** Every chapter placed by *what it means* (a computed text
  embedding — **Tier 3, not authoritative**). The field is calm by default; **hover a chapter to
  reveal only its sourced cross-references** (Tier 2), coloured teal→gold by meaning-distance — a
  **gold link is *surprising*** (a sourced connection that is right yet spans a wide meaning gap).
  A **meaning⇄kinship** toggle re-lays-out the same chapters from the cross-ref graph.
- **Chord view (`chord.html`).** The 66 books on a ring, isolating the ~129k cross-Testament arcs;
  click a book to drill to verse level, hover an arc to read both verse texts and its provenance.

Everything honours *attribute-never-assert*: only sourced `review_status='ok'` edges are
authoritative, and the terrain's positions are explicitly *"computed, not authoritative."*

🧑‍💻 **Code & build:** <https://github.com/LucasGalhardoLima/sinew>
🗃️ **Dataset:** <https://huggingface.co/datasets/LucasGalhardoLima/sinew>

Licensed CC-BY-4.0; cross-references © OpenBible.info (CC-BY); Bible text is public domain (WEB).
