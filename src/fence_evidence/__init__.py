"""Source-preserving evidence system for the vinyl fence BOM corpus.

The corpus (manuals/, china/manuals/, data/, schema/) is READ-ONLY.
All generated output goes to workspace/.

Optional third-party extraction backends are installed into
``workspace/pylibs`` (git-ignored) and picked up here.  Every one of them is
optional: the pipeline degrades to poppler + tesseract + the standard library
when they are absent, and records which backend produced each result.
"""
from __future__ import annotations

import sys
from pathlib import Path

__version__ = "1.0.0"

_PYLIBS = Path(__file__).resolve().parents[2] / "workspace" / "pylibs"
if _PYLIBS.is_dir() and str(_PYLIBS) not in sys.path:
    sys.path.append(str(_PYLIBS))
