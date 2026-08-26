"""Tier-1 text, pt-BR translations layered onto the WEB-canonical `verses` set — Bíblia Livre
(BLIVRE, N4 edition) and Nova Bíblia de Acesso Livre (NVA).

BLIVRE source: official VPL release (github.com/blivre/BibliaLivre, 2018.2.0), CC BY 4.0 Brasil
(Diego Santos, Mario Sérgio, Marco Teles). Unlike `text.load_web` (which DEFINES the canonical
`verses` set), each of these is a second/third `texts` row per verse_id — the canonical set stays
WEB-derived, each pt translation only fills in wherever it has aligned coverage.

A full 1189-chapter verse-count audit against WEB (this repo, 2026-08-11) found exactly one
real divergence: `Rom.16` (WEB 24 verses, BLIVRE 27 — the Romans 16:25-27 doxology, present in
BLIVRE's Byzantine-adjacent tradition, absent as separately-numbered verses in WEB's). BLIVRE
itself marks its own v24 there as omitted (a bare "—"). Both of those are handled generically
below (unaddressable verse_id / empty-placeholder text), not special-cased — `KNOWN_DIVERGENT_CHAPTERS`
exists only so a *future*, unexpected divergence fails loud instead of silently misaligning text.

NVA source: biblia.publica (github.com/Projeto-Euaggelion/biblia.publica) JSON export of the
Nova Bíblia de Acesso Livre, CC BY-SA 4.0 — a MAST-program translation (Wycliffe Associates
methodology, unfoldingWord Greek NT + Masoretic OT, 3-reviewer-per-stage process documented at
biblianva.com.br/timeline). biblia.publica is an aggregator, not the primary host (that's
git.door43.org/alexandre_brazil) — used here because it already ships schema-validated,
per-book JSON with a declared `filesHash`; if that ever proves unreliable the same audit done
for BLIVRE (compare against a second independent copy) should be repeated before trusting it
further. NVA renders the Tetragrammaton as "Yahweh" (not "SENHOR", unlike BLIVRE and most pt-BR
tradition) and capitalizes divine pronouns — a translation-philosophy choice, left as-is; this
loader does not editorialize the text, only maps books and validates versification. A same-style
audit against WEB (2026-08-26) found exactly four real divergences, all well-known
textual/versification variants, none a mapping bug — see `KNOWN_DIVERGENT_CHAPTERS_NVA`.
"""
import json
import re

# BLIVRE's VPL book codes -> sinew's own abbreviations (books.CANONICAL). NOT the same as
# books.CPH2ABBR: BLIVRE's codes diverge from Copenhagen's in several places (JOH not JHN,
# MAR not MRK, SOL not SNG, EZE not EZK, JOE not JOL, NAH not NAM, PHI not PHP, JAM not JAS,
# 1JO/2JO/3JO not 1JN/2JN/3JN) — verified by diffing the full 66-code sets, not assumed.
BLIVRE_TO_SINEW = {
    "GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh",
    "JDG": "Judg", "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs",
    "1CH": "1Chr", "2CH": "2Chr", "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job",
    "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl", "SOL": "Song", "ISA": "Isa", "JER": "Jer",
    "LAM": "Lam", "EZE": "Ezek", "DAN": "Dan", "HOS": "Hos", "JOE": "Joel", "AMO": "Amos",
    "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAH": "Nah", "HAB": "Hab", "ZEP": "Zeph",
    "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal",
    "MAT": "Matt", "MAR": "Mark", "LUK": "Luke", "JOH": "John", "ACT": "Acts", "ROM": "Rom",
    "1CO": "1Cor", "2CO": "2Cor", "GAL": "Gal", "EPH": "Eph", "PHI": "Phil", "COL": "Col",
    "1TH": "1Thess", "2TH": "2Thess", "1TI": "1Tim", "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm",
    "HEB": "Heb", "JAM": "Jas", "1PE": "1Pet", "2PE": "2Pet", "1JO": "1John", "2JO": "2John",
    "3JO": "3John", "JUD": "Jude", "REV": "Rev",
}
assert len(BLIVRE_TO_SINEW) == 66

# (book, chapter) pairs where BLIVRE's verse count is known and expected to differ from WEB's —
# see module docstring. Any OTHER chapter-count mismatch is a build-time error, not a silent skip.
KNOWN_DIVERGENT_CHAPTERS = {("Rom", 16)}

_LINE = re.compile(r'^([1-3]?[A-Z]{2,3})\s+(\d+):(\d+)\s+(.*)$')
_HYPHEN_BRACKET = re.compile(r'-\s+\[')
_COLON_NO_SPACE = re.compile(r':(?=[^\s\d])')
_PLACEHOLDER = re.compile(r'^[\s—\-–]*$')   # a bare dash (or nothing) marks an omitted verse


def _clean(text):
    """Fix two BLIVRE VPL export artifacts (verified against the full text, not per-verse):
    supplied-word brackets (`[procedem]`) and a missing space after glued psalm titles
    (`"Salmo de Davi:O SENHOR..."`). Both are export formatting, not translation content."""
    text = _HYPHEN_BRACKET.sub('-', text)
    text = text.replace('[', '').replace(']', '')
    text = _COLON_NO_SPACE.sub(': ', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def load_blivre(path, verse_set, chapter_verse_counts):
    """Return (texts, stats).

    texts: [(verse_id, 'BLIVRE', text)] — only for verse_ids present in `verse_set` (WEB's
    canonical space) with real (non-placeholder) BLIVRE content.
    stats: counts for build-log transparency (see build.py) — nothing here is silently dropped.
    """
    raw = {}
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            m = _LINE.match(line.rstrip("\n"))
            if not m:
                continue
            code, ch, v, text = m.groups()
            abbr = BLIVRE_TO_SINEW.get(code)
            if abbr is None:
                continue
            raw.setdefault(abbr, {}).setdefault(int(ch), {})[int(v)] = _clean(text)

    # Fail loud on any unexpected versification drift (see KNOWN_DIVERGENT_CHAPTERS).
    unexpected = []
    for abbr, chapters in raw.items():
        for ch, verses in chapters.items():
            blivre_max = max(verses)
            web_max = chapter_verse_counts.get((abbr, ch))
            if web_max is not None and blivre_max != web_max and (abbr, ch) not in KNOWN_DIVERGENT_CHAPTERS:
                unexpected.append((abbr, ch, web_max, blivre_max))
    assert not unexpected, f"unexpected BLIVRE/WEB verse-count drift: {unexpected}"

    texts = []
    stats = {"parsed": 0, "unaddressable": 0, "placeholder": 0, "inserted": 0}
    for abbr, chapters in raw.items():
        for ch, verses in chapters.items():
            for v, text in verses.items():
                stats["parsed"] += 1
                vid = f"{abbr}.{ch}.{v}"
                if vid not in verse_set:
                    stats["unaddressable"] += 1
                    continue
                if _PLACEHOLDER.match(text):
                    stats["placeholder"] += 1
                    continue
                texts.append((vid, "BLIVRE", text))
                stats["inserted"] += 1
    return texts, stats


# biblia.publica's own NVA book codes -> sinew's abbreviations (books.CANONICAL). Lowercase,
# distinct scheme from both Copenhagen and BLIVRE's — verified by diffing the full 66-code sets
# against `books.BOOK_NUM.keys()` (see `test_nva_book_mapping_is_bijective_onto_sinew_canon`),
# not assumed.
NVA_TO_SINEW = {
    "gn": "Gen", "ex": "Exod", "lv": "Lev", "nm": "Num", "dt": "Deut", "js": "Josh",
    "jz": "Judg", "rt": "Ruth", "1sm": "1Sam", "2sm": "2Sam", "1rs": "1Kgs", "2rs": "2Kgs",
    "1cr": "1Chr", "2cr": "2Chr", "ed": "Ezra", "ne": "Neh", "et": "Esth", "job": "Job",
    "sl": "Ps", "pv": "Prov", "ec": "Eccl", "ct": "Song", "is": "Isa", "jr": "Jer",
    "lm": "Lam", "ez": "Ezek", "dn": "Dan", "os": "Hos", "jl": "Joel", "am": "Amos",
    "ob": "Obad", "jn": "Jonah", "mq": "Mic", "na": "Nah", "hc": "Hab", "sf": "Zeph",
    "ag": "Hag", "zc": "Zech", "ml": "Mal",
    "mt": "Matt", "mc": "Mark", "lc": "Luke", "jo": "John", "at": "Acts", "rm": "Rom",
    "1co": "1Cor", "2co": "2Cor", "gl": "Gal", "ef": "Eph", "fp": "Phil", "cl": "Col",
    "1ts": "1Thess", "2ts": "2Thess", "1tm": "1Tim", "2tm": "2Tim", "tt": "Titus", "fm": "Phlm",
    "hb": "Heb", "tg": "Jas", "1pe": "1Pet", "2pe": "2Pet", "1jo": "1John", "2jo": "2John",
    "3jo": "3John", "jd": "Jude", "ap": "Rev",
}
assert len(NVA_TO_SINEW) == 66

# (book, chapter) pairs where NVA's verse count is known and expected to differ from WEB's —
# see module docstring. Any OTHER chapter-count mismatch is a build-time error, not a silent skip.
KNOWN_DIVERGENT_CHAPTERS_NVA = {
    ("Jer", 43),    # NVA lacks v13 — biblia.publica's own meta.json documents this as a source
                    # gap ("marcador \\v presente mas sem conteúdo real na fonte"), not our bug.
    ("Rom", 16),    # same Romans 16:25-27 doxology as BLIVRE — see module docstring.
    ("3John", 1),   # NVA splits the final verse into 14+15; WEB keeps it as one v14. A known
                    # translation-level split, not a digitization error.
    ("Rev", 12),    # NVA counts "E fiquei em pé sobre a areia do mar" as 12:18; WEB attaches the
                    # same clause to the start of chapter 13. A known chapter-boundary variant.
}


def load_nva(path, verse_set, chapter_verse_counts):
    """Return (texts, stats).

    texts: [(verse_id, 'NVA', text)] — only for verse_ids present in `verse_set` (WEB's
    canonical space). stats: counts for build-log transparency — nothing here is silently
    dropped. `path` is the combined `data/raw/nva_pt.json`: a JSON array of 66 book objects
    (biblia.publica's own per-book schema, concatenated), not a single flat file like BLIVRE's.
    """
    books = json.load(open(path, encoding="utf-8"))

    # Fail loud on any unexpected versification drift (see KNOWN_DIVERGENT_CHAPTERS_NVA).
    unexpected = []
    for b in books:
        abbr = NVA_TO_SINEW[b["abbrev"]]
        for ch in b["chapters"]:
            cn = ch["number"]
            vnums = [v["number"] for v in ch["verses"]]
            if not vnums:
                continue
            nva_max = max(vnums)
            web_max = chapter_verse_counts.get((abbr, cn))
            if web_max is not None and nva_max != web_max and (abbr, cn) not in KNOWN_DIVERGENT_CHAPTERS_NVA:
                unexpected.append((abbr, cn, web_max, nva_max))
    assert not unexpected, f"unexpected NVA/WEB verse-count drift: {unexpected}"

    texts = []
    stats = {"parsed": 0, "unaddressable": 0, "inserted": 0}
    for b in books:
        abbr = NVA_TO_SINEW[b["abbrev"]]
        for ch in b["chapters"]:
            cn = ch["number"]
            for v in ch["verses"]:
                stats["parsed"] += 1
                vid = f"{abbr}.{cn}.{v['number']}"
                if vid not in verse_set:
                    stats["unaddressable"] += 1
                    continue
                text = " ".join(v["text"].split())
                texts.append((vid, "NVA", text))
                stats["inserted"] += 1
    return texts, stats
