"""Tier-1 text + the authoritative canonical verse list, from the public-domain World English
Bible (eng/KJV-numbered). The set of verses we hold text for IS the `verses` table, which
guarantees the P0 invariant "every canonical verse has >=1 text".

Source: getbible.net v2 `web.json` (mirrors eBible.org/web/, Public Domain). Book `nr` 1..66 is
canonical Protestant order, so nr -> abbreviation by index into books.BOOKS.
"""
import json
from .books import BOOKS, BOOK_NUM


def load_web(path):
    """Return (verses, texts, chapter_verse_counts).

    verses: [(book, chapter, verse, canonical_order)]   (canonical_order = 1..N in canon order)
    texts:  [(verse_id, 'WEB', text)]
    chapter_verse_counts: {(book, chapter): max_verse}
    """
    d = json.load(open(path))
    assert d.get("distribution_license", "").strip().lower().startswith("public"), \
        f"WEB source is not public domain: {d.get('distribution_license')!r}"
    books = d["books"]
    assert len(books) == 66, f"expected 66 books, got {len(books)}"

    verses, texts, counts = [], [], {}
    order = 0
    for b in books:
        abbr = BOOKS[b["nr"] - 1]
        for ch in b["chapters"]:
            c = int(ch["chapter"])
            for v in ch["verses"]:
                n = int(v["verse"])
                txt = " ".join((v.get("text") or "").split())
                if not txt:
                    continue
                order += 1
                verses.append((abbr, c, n, order))
                texts.append((f"{abbr}.{c}.{n}", "WEB", txt))
                counts[(abbr, c)] = max(counts.get((abbr, c), 0), n)
    # sanity: canonical order is strictly increasing by (book_num, chap, verse)
    keyed = sorted(verses, key=lambda r: (BOOK_NUM[r[0]], r[1], r[2]))
    assert [r[3] for r in keyed] == list(range(1, len(verses) + 1)), \
        "WEB verses are not in canonical order"
    return verses, texts, counts
