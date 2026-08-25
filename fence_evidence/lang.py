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

UNDETERMINED = ("und", "unknown")


def detect_lang(text: str | None) -> tuple[str, str]:
    """Return ``(lang, basis)`` for a piece of source text.

    ``lang`` is a BCP-47 tag: ``en``, ``zh``, or ``und`` when there is nothing
    to go on. ``basis`` is ``measured | assumed | unknown`` and is never
    ``measured`` here -- see the module docstring.
    """
    if not text or not text.strip():
        return UNDETERMINED
    if _CJK.search(text):
        # Mixed CJK and Latin is normal on a Chinese page carrying a model
        # number. The CJK is the signal; the Latin is a product code.
        return ("zh", "assumed")
    if _LETTER_RUN.search(text):
        return ("en", "assumed")
    # Digits, punctuation, and OCR noise with no word-like run in it. `30" 1-1/2`
    # is a real measurement and has no language; saying `en` would invent one.
    return UNDETERMINED
