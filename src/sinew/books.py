"""Canonical 66-book order, code maps, and reference parsers shared across the pipeline.

verse_id format (our canonical, eng-numbered): "Book.Chapter.Verse" e.g. "Gen.1.1", "1Cor.5.7".
Book abbreviations match OpenBible's OSIS-style tokens (no internal dots), so splitting on "."
yields exactly [book, chapter, verse]. Copenhagen Alliance refs use uppercase 3-letter codes
("PSA 3:0-8") — translated here to our abbreviations.
"""

# (abbrev, full name, Copenhagen 3-letter code) in canonical Protestant order, book number = index+1
CANONICAL = [
    ("Gen", "Genesis", "GEN"), ("Exod", "Exodus", "EXO"), ("Lev", "Leviticus", "LEV"),
    ("Num", "Numbers", "NUM"), ("Deut", "Deuteronomy", "DEU"), ("Josh", "Joshua", "JOS"),
    ("Judg", "Judges", "JDG"), ("Ruth", "Ruth", "RUT"), ("1Sam", "1 Samuel", "1SA"),
    ("2Sam", "2 Samuel", "2SA"), ("1Kgs", "1 Kings", "1KI"), ("2Kgs", "2 Kings", "2KI"),
    ("1Chr", "1 Chronicles", "1CH"), ("2Chr", "2 Chronicles", "2CH"), ("Ezra", "Ezra", "EZR"),
    ("Neh", "Nehemiah", "NEH"), ("Esth", "Esther", "EST"), ("Job", "Job", "JOB"),
    ("Ps", "Psalms", "PSA"), ("Prov", "Proverbs", "PRO"), ("Eccl", "Ecclesiastes", "ECC"),
    ("Song", "Song of Solomon", "SNG"), ("Isa", "Isaiah", "ISA"), ("Jer", "Jeremiah", "JER"),
    ("Lam", "Lamentations", "LAM"), ("Ezek", "Ezekiel", "EZK"), ("Dan", "Daniel", "DAN"),
    ("Hos", "Hosea", "HOS"), ("Joel", "Joel", "JOL"), ("Amos", "Amos", "AMO"),
    ("Obad", "Obadiah", "OBA"), ("Jonah", "Jonah", "JON"), ("Mic", "Micah", "MIC"),
    ("Nah", "Nahum", "NAM"), ("Hab", "Habakkuk", "HAB"), ("Zeph", "Zephaniah", "ZEP"),
    ("Hag", "Haggai", "HAG"), ("Zech", "Zechariah", "ZEC"), ("Mal", "Malachi", "MAL"),
    ("Matt", "Matthew", "MAT"), ("Mark", "Mark", "MRK"), ("Luke", "Luke", "LUK"),
    ("John", "John", "JHN"), ("Acts", "Acts", "ACT"), ("Rom", "Romans", "ROM"),
    ("1Cor", "1 Corinthians", "1CO"), ("2Cor", "2 Corinthians", "2CO"), ("Gal", "Galatians", "GAL"),
    ("Eph", "Ephesians", "EPH"), ("Phil", "Philippians", "PHP"), ("Col", "Colossians", "COL"),
    ("1Thess", "1 Thessalonians", "1TH"), ("2Thess", "2 Thessalonians", "2TH"),
    ("1Tim", "1 Timothy", "1TI"), ("2Tim", "2 Timothy", "2TI"), ("Titus", "Titus", "TIT"),
    ("Phlm", "Philemon", "PHM"), ("Heb", "Hebrews", "HEB"), ("Jas", "James", "JAS"),
    ("1Pet", "1 Peter", "1PE"), ("2Pet", "2 Peter", "2PE"), ("1John", "1 John", "1JN"),
    ("2John", "2 John", "2JN"), ("3John", "3 John", "3JN"), ("Jude", "Jude", "JUD"),
    ("Rev", "Revelation", "REV"),
]
assert len(CANONICAL) == 66

BOOKS      = [a for a, _, _ in CANONICAL]
BOOK_NUM   = {a: i + 1 for i, a in enumerate(BOOKS)}          # 1..66
BOOK_NAME  = {a: n for a, n, _ in CANONICAL}
CPH2ABBR   = {c: a for a, _, c in CANONICAL}
ABBR2CPH   = {a: c for a, _, c in CANONICAL}
NT         = set(BOOKS[39:])                                  # Matt..Rev
def testament(book): return "NT" if book in NT else "OT"


# Literary/genre sections — used to colour the meaning-terrain view (sinew.embed / meaning.viz.js).
# Position there encodes computed meaning (Tier 3); section is just a familiar colour key, not a claim.
SECTIONS = [
    ("Law",          "Gen Exod Lev Num Deut".split(),                                              "#2a6f97"),
    ("History",      "Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth".split(),         "#468faf"),
    ("Wisdom",       "Job Ps Prov Eccl Song".split(),                                               "#61a5c2"),
    ("Prophets",     "Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal".split(), "#89c2d9"),
    ("Gospels/Acts", "Matt Mark Luke John Acts".split(),                                            "#e76f51"),
    ("Epistles",     "Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude".split(), "#f4a261"),
    ("Revelation",   ["Rev"],                                                                       "#e9c46a"),
]
assert sum(len(bs) for _, bs, _ in SECTIONS) == 66
_SECTION_OF    = {b: name for name, bs, _ in SECTIONS for b in bs}
_SECTION_COLOR = {b: col  for _, bs, col in SECTIONS for b in bs}
def section(book):       return _SECTION_OF.get(book)        # e.g. 'Wisdom'; None if unknown
def section_color(book): return _SECTION_COLOR.get(book)     # hex for the section; None if unknown


def parse_id(verse_id):
    """'1Cor.5.7' -> ('1Cor', 5, 7). Returns None if malformed/unknown book."""
    p = verse_id.split(".")
    if len(p) != 3 or p[0] not in BOOK_NUM:
        return None
    try:
        return (p[0], int(p[1]), int(p[2]))
    except ValueError:
        return None


def chapter_of(ref):
    """Head chapter of a (possibly ranged) ref: 'Ps.148.4-Ps.148.5' -> ('Ps', 148)."""
    p = ref.split("-")[0].split(".")
    if len(p) < 2 or p[0] not in BOOK_NUM:
        return None
    try:
        return (p[0], int(p[1]))
    except ValueError:
        return None


def expand_openbible_ref(ref, chapter_verse_counts):
    """Expand an OpenBible reference (single or range) into a list of 'Book.Ch.V' ids.

    'Rom.1.19-Rom.1.20' -> ['Rom.1.19','Rom.1.20']; cross-chapter ranges expand using
    chapter_verse_counts[(book,chap)] = max verse. Single refs return a one-element list.
    Returns [] for unparseable input.
    """
    parts = ref.split("-")
    a = parse_id(parts[0])
    if a is None:
        return []
    if len(parts) == 1:
        return [f"{a[0]}.{a[1]}.{a[2]}"]
    b = parse_id(parts[1])
    if b is None or b[0] != a[0]:
        return [f"{a[0]}.{a[1]}.{a[2]}"]          # degenerate range -> head only
    book = a[0]
    out = []
    ch, vs = a[1], a[2]
    while (ch, vs) <= (b[1], b[2]):
        out.append(f"{book}.{ch}.{vs}")
        maxv = chapter_verse_counts.get((book, ch))
        if ch == b[1]:
            vs += 1
        elif maxv and vs >= maxv:
            ch, vs = ch + 1, 1
        else:
            vs += 1
        if len(out) > 400:                         # safety against pathological ranges
            break
    return out


def parse_cph_ref(cph_ref):
    """Expand a Copenhagen ref into [(abbrev, chap, verse), ...], translating the book code.

    Forms: 'PSA 3:1' | 'PSA 3:0-8' (same chapter) | 'EXO 8:1-4'->one chapter |
    'JOL 2:28-32' | cross-chapter 'GEN 32:1-32'->'GEN 32:2-33' handled per side.
    Subverse markers ('!a') are stripped to the base verse.
    """
    cph_ref = cph_ref.replace("!", "").strip()
    try:
        code, rest = cph_ref.split(" ", 1)
    except ValueError:
        return []
    abbr = CPH2ABBR.get(code)
    if abbr is None:
        return []                                  # deuterocanon / unknown -> out of scope

    def one(token):                                 # 'C:V' -> (chap, verse)
        c, v = token.split(":")
        return int(c), int(v)

    if "-" not in rest:
        c, v = one(rest)
        return [(abbr, c, v)]
    lo, hi = rest.split("-", 1)
    c1, v1 = one(lo)
    hi = hi if ":" in hi else f"{c1}:{hi}"          # 'C:V-V' -> same chapter
    c2, v2 = one(hi)
    out = []
    c, v = c1, v1
    # within-chapter span, or simple cross-chapter span assuming contiguous numbering
    while (c, v) <= (c2, v2):
        out.append((abbr, c, v))
        if c == c2:
            v += 1
        else:
            v += 1                                  # walk; chapter rollover handled by mapping pairs
        if len(out) > 400:
            break
    return out
