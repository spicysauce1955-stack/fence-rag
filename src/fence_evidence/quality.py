"""Text-quality checks that decide whether a source text layer can be trusted.

Character count alone is not enough.  Several PDFs in this corpus carry a text
layer that decodes to mojibake because the embedded font has no usable
ToUnicode map — ``bm|o|_;]uom7`` where the page reads ``into the ground``.
Those files look like clean text-layer PDFs to a length-based heuristic, so
they need a separate test before their text is trusted; when it fails, the page
takes the OCR path and the rejection is recorded as a quality issue.

Two signals, measured per page and required together:

* ``control_ratio`` — C0/C1 control characters per character.  A well-formed
  text layer has none.
* ``ascii_token_ratio`` — share of word-like tokens that are pure ASCII.  A
  legitimate non-English page (the China track) scores high here even when it
  has control characters, which is why one signal alone is not enough.
"""
from __future__ import annotations

CONTROL_RATIO_LIMIT = 0.005
ASCII_TOKEN_RATIO_LIMIT = 0.85
CJK_LEGIT_SHARE = 0.20
MIN_CHARS_FOR_JUDGEMENT = 200


def control_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(1 for c in text
              if (ord(c) < 32 and c not in "\n\r\t\f") or 0x80 <= ord(c) <= 0x9F)
    return bad / len(text)


def ascii_token_ratio(text: str) -> float:
    tokens = [t for t in text.split() if len(t) >= 3 and any(c.isalpha() for c in t)]
    if not tokens:
        return 1.0
    pure = sum(1 for t in tokens if all(ord(c) < 128 for c in t))
    return pure / len(tokens)


def cjk_share(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for c in text
              if 0x3000 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF)
    return cjk / len(text)


def text_quality(text: str) -> dict:
    return {"chars": len(text), "control_ratio": round(control_ratio(text), 5),
            "ascii_token_ratio": round(ascii_token_ratio(text), 4),
            "cjk_share": round(cjk_share(text), 4)}


def is_mojibake(text: str) -> tuple[bool, dict]:
    """True when a text layer exists but does not decode to readable language."""
    q = text_quality(text)
    if q["chars"] < MIN_CHARS_FOR_JUDGEMENT:
        return False, q
    if q["cjk_share"] >= CJK_LEGIT_SHARE:
        # a genuinely Chinese page scores low on ascii_token_ratio by definition
        return False, q
    bad = (q["control_ratio"] > CONTROL_RATIO_LIMIT
           and q["ascii_token_ratio"] < ASCII_TOKEN_RATIO_LIMIT)
    return bad, q
