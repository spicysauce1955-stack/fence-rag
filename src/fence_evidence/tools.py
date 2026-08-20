"""Thin, non-shell wrappers around the external extraction tools.

Every call passes an argument *list* — no shell, ever — so nothing that appears
inside a corpus document can be interpreted as a command (prohibition 10).
"""
from __future__ import annotations

import functools
import subprocess
from pathlib import Path


class ToolError(RuntimeError):
    pass


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    if not isinstance(cmd, list) or not all(isinstance(c, str) for c in cmd):
        raise TypeError("commands must be a list of strings; shell use is forbidden")
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                          timeout=timeout, shell=False)


@functools.lru_cache(maxsize=1)
def tool_versions() -> dict[str, str]:
    v: dict[str, str] = {}
    for name, cmd in (("pdftotext", ["pdftotext", "-v"]),
                      ("pdftoppm", ["pdftoppm", "-v"]),
                      ("pdfinfo", ["pdfinfo", "-v"]),
                      ("tesseract", ["tesseract", "--version"])):
        try:
            r = run(cmd, timeout=30)
            out = (r.stdout or "") + (r.stderr or "")
            v[name] = out.strip().splitlines()[0] if out.strip() else "unknown"
        except Exception as e:  # tool absent
            v[name] = f"unavailable: {e.__class__.__name__}"
    try:
        import pdfplumber  # noqa
        v["pdfplumber"] = pdfplumber.__version__
    except Exception:
        v["pdfplumber"] = "unavailable"
    try:
        import PIL
        v["pillow"] = PIL.__version__
    except Exception:
        v["pillow"] = "unavailable"
    import sys
    v["python"] = sys.version.split()[0]
    return v


def have_pdfplumber() -> bool:
    return tool_versions().get("pdfplumber", "unavailable") != "unavailable"


def render_page(pdf: Path, page_no: int, out_prefix: Path, dpi: int = 200) -> Path:
    """Render one PDF page to PNG via pdftoppm. Returns the written path."""
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    r = run(["pdftoppm", "-r", str(dpi), "-png", "-f", str(page_no), "-l", str(page_no),
             "-singlefile", str(pdf), str(out_prefix)])
    target = out_prefix.with_suffix(".png")
    if r.returncode != 0 or not target.exists():
        raise ToolError(f"pdftoppm failed for {pdf}:{page_no}: {r.stderr[:400]}")
    return target


def ocr_hocr(image: Path, psm: int = 1, lang: str = "eng") -> str:
    """Run tesseract and return hOCR XML."""
    r = run(["tesseract", str(image), "stdout", "--psm", str(psm), "-l", lang, "hocr"])
    if r.returncode != 0:
        raise ToolError(f"tesseract failed on {image}: {r.stderr[:400]}")
    return r.stdout
