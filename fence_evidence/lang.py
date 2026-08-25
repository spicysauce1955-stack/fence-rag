"""What language a piece of source text is in, and how confident that is.

Obligation 10 requires `lang` on published text and forbids normalising it. The
obligation exists to stop a guess being published as a fact, so this module
returns the guess *and its basis* together, and there is no way to get one
without the other.

**Do not derive language from `corpus_track`.** That was the obvious
implementation and it is wrong: the track is a standards regime -- GB rather
than ASTM, metric rather than imperial -- not a language. Measured against this
corpus, there are *zero* CJK-bearing elements, and the China-track documents are
English-language export catalogues whose strongest text reads
``PREFACE 05 OUR ADVANTAGES``. The shortcut would have stamped ``zh`` on 2,809
English elements. See docs/state-and-gaps.md G32.

What is honest here: **script is measured, language is inferred from script.**
Unicode ranges tell us reliably whether text is CJK or Latin. They cannot tell
English from German, and tesseract on this machine has only ``eng`` installed
with no way to add more. So every language this returns is ``assumed``, and
``measured`` stays reserved for a real language identifier that does not exist
yet.
"""
from __future__ import annotations

import re

# CJK unified ideographs, the extension A block, and compatibility ideographs.
# Deliberately not the kana blocks: Japanese would be `ja`, not `zh`, and this
# corpus has no Japanese in it to test against.
_CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
# A *run* of two or more letters, not a single letter. OCR noise off a scanned
# drawing is full of isolated stray glyphs -- `-—— e. —— : 4` is real text from
# the Showtech catalogue -- and one letter is not evidence of a language. Two
# adjacent ones are the cheapest thing that behaves like a word.
_LETTER_RUN = re.compile(r"[^\W\d_]{2,}", re.UNICODE)

# Function words, not content words. A borrowed noun proves nothing -- "panel de
# force" is English -- but a text that reaches for `des`, `une` and `pour` is
# reaching for French grammar, and grammar is not borrowed one word at a time.
# Two independent hits are required, so a single stray cannot flip a language.
#
# This exists because the corpus measurably needs it: the Barrette install guides
# print English on pages 2-13 and French or Spanish on 14-22 of the SAME PDF, so
# 137 warning units were tagged `en` on nothing but "it uses the Latin alphabet".
# Obligation 10 exempts source warnings from translation on the strength of this
# tag; a wrong tag defeats the mechanism the exemption relies on.
_MARKERS = {
    "fr": (r"avertissement", r"\bdes\b", r"\bune\b", r"\bpour\b", r"\bvous\b",
           r"\bles\b", r"\best\b", r"\bdu\b", r"\bsur\b", r"\bavec\b",
           r"\bpeut\b", r"\blors\b", r"\btoujours\b", r"\bproduit\b",
           r"\bcauser\b", r"\bmauvaise\b", r"\bs\u00e9curit\u00e9\b", r"\bl'"),
    "es": (r"advertencia", r"\blos\b", r"\blas\b", r"\bpara\b", r"\buna\b",
           r"\bdel\b", r"\bcon\b", r"\bpuede\b", r"\bsiempre\b",
           r"\bproducto\b", r"\bincorrecta\b", r"\butilice\b", r"\bseguridad\b",
           r"\besta\b", r"\bque\b"),
}
_MARKER_RE = {lang: [re.compile(p, re.IGNORECASE) for p in pats]
              for lang, pats in _MARKERS.items()}
MIN_MARKERS = 2

UNDETERMINED = ("und", "unknown")


def detect_lang(text: str | None) -> tuple[str, str]:
    """Return ``(lang, basis)`` for a piece of source text.

    ``lang`` is a BCP-47 tag: ``en``, ``fr``, ``es``, ``zh``, or ``und`` when
    there is nothing to go on. ``basis`` is ``measured | assumed | unknown`` and is never
    ``measured`` here -- see the module docstring.
    """
    if not text or not text.strip():
        return UNDETERMINED
    if _CJK.search(text):
        # Mixed CJK and Latin is normal on a Chinese page carrying a model
        # number. The CJK is the signal; the Latin is a product code.
        return ("zh", "assumed")
    if _LETTER_RUN.search(text):
        # Score every candidate, then require a clear winner. Scoring all of them
        # rather than returning on the first hit stops ordering from deciding a
        # close call -- `que` and `con` appear in both Spanish and French text.
        scores = {lang: sum(1 for r in pats if r.search(text))
                  for lang, pats in _MARKER_RE.items()}
        best = max(scores, key=lambda k: scores[k])
        if scores[best] >= MIN_MARKERS and scores[best] > max(
                [v for k, v in scores.items() if k != best] or [0]):
            return (best, "assumed")
        return ("en", "assumed")
    # Digits, punctuation, and OCR noise with no word-like run in it. `30" 1-1/2`
    # is a real measurement and has no language; saying `en` would invent one.
    return UNDETERMINED
