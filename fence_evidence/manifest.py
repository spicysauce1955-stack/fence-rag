"""Phase 0 — corpus inspection.

Builds ``workspace/catalog/corpus-manifest.jsonl`` without touching a single
source file.  One JSON object per corpus file, carrying identity, technical
characteristics (page count, text-layer availability, scan suspicion) and the
metadata the hand-curated document indexes already know about it.
"""
from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .ids import doc_id_for, sha256_file
from .paths import (CORPUS_ROOTS, DOCUMENT_INDEXES, FETCH_HINT, MANIFEST_PATH,
                    REPO_ROOT, is_lfs_pointer, lfs_pointer_info, open_write, rel)

# Files with a text layer this thin are treated as scans needing OCR.
SCAN_CHARS_PER_PAGE = 60
TEXT_LAYER_MIN_CHARS = 100

PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
DOCX_SUFFIXES = {".docx"}


def _run(cmd, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)


def _pdfinfo(path: Path) -> dict:
    out = _run(["pdfinfo", str(path)]).stdout
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def _page_char_counts(path: Path, pages: int) -> list[int]:
    """Characters of embedded text per page (0 for image-only pages)."""
    counts = []
    for p in range(1, pages + 1):
        r = _run(["pdftotext", "-f", str(p), "-l", str(p), "-layout", str(path), "-"])
        counts.append(len(r.stdout.strip()))
    return counts


def _load_curated_metadata() -> dict[str, dict]:
    """local_path -> curated metadata, from the two documents-index.json files."""
    meta: dict[str, dict] = {}
    for idx_path in DOCUMENT_INDEXES:
        if not idx_path.is_file():
            continue
        with open(idx_path) as f:
            idx = json.load(f)
        for row in idx.get("documents", []):
            lp = row.get("local_path")
            if not lp:
                continue
            # Later entries must not silently clobber earlier ones: keep both.
            existing = meta.get(lp)
            if existing:
                existing.setdefault("_duplicate_index_entries", []).append(row)
            else:
                meta[lp] = dict(row)
    return meta


_SUPERSEDED_RE = re.compile(
    r"\b(superseded|expired|previous|prior|legacy|obsolete|replaced)\b", re.I)
_ACTIVE_RE = re.compile(r"\b(current|active)\b", re.I)
_DATE_RANGE_RE = re.compile(r"(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}")
_ISSUE_RE = re.compile(
    r"(?:approved|issued|issue date|effective)[:\s]*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4})", re.I)
_EXPIRY_RE = re.compile(
    r"(?:expires|expiration|expiry)[:\s]*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+ \d{1,2},? \d{4}|\d{4})", re.I)


def _version_status(rel_path: str, curated: dict) -> tuple[str, str]:
    """(status, why).  Conservative: 'unknown' unless the corpus says otherwise."""
    hay = " ".join(filter(None, [
        rel_path, curated.get("title") or "", curated.get("date_or_version") or ""]))
    if _SUPERSEDED_RE.search(hay):
        return "superseded", "keyword in title/filename"
    if _ACTIVE_RE.search(hay):
        return "active", "keyword in title/filename"
    return "unknown", "no explicit version marker in curated metadata"


def _dates(curated: dict) -> tuple[str | None, str | None]:
    dv = curated.get("date_or_version") or ""
    issue = _ISSUE_RE.search(dv)
    expiry = _EXPIRY_RE.search(dv)
    return (issue.group(1) if issue else None, expiry.group(1) if expiry else None)


def _manufacturer_from_path(rel_path: str) -> str | None:
    parts = Path(rel_path).parts
    if parts and parts[0] == "manuals" and len(parts) > 1:
        return parts[1]
    if len(parts) > 2 and parts[0] == "china" and parts[1] == "manuals":
        return f"china/{parts[2]}"
    return None


def inspect_file(args) -> dict:
    """Inspect a single corpus file.  Read-only; safe to run in a subprocess."""
    path_str, curated = args
    path = Path(path_str)
    rp = rel(path)
    stat = path.stat()
    suffix = path.suffix.lower()
    rec: dict = {
        "doc_id": doc_id_for(rp),
        "source_path": rp,
        "sha256": sha256_file(path),
        "file_size_bytes": stat.st_size,
        "file_type": suffix.lstrip("."),
        "page_count": None,
        "text_layer_available": None,
        "text_chars_total": None,
        "text_chars_per_page": None,
        "pages_with_text": None,
        "suspected_scan": None,
        "extraction_method": None,
        "manufacturer": curated.get("manufacturer") or _manufacturer_from_path(rp),
        "product_family": curated.get("model_or_line"),
        "doc_type": curated.get("doc_type") or "unspecified",
        "title": curated.get("title"),
        "source_url": curated.get("url"),
        "date_or_version": curated.get("date_or_version"),
        "issue_date": None,
        "expiration_date": None,
        "version_status": "unknown",
        "version_status_basis": None,
        "in_curated_index": bool(curated),
        "structural_subdir": "/structural/" in "/" + rp,
        "corpus_track": "china" if rp.startswith("china/") else "us",
        "processing_state": "pending",
        "inspection_notes": [],
    }
    rec["issue_date"], rec["expiration_date"] = _dates(curated)
    rec["version_status"], rec["version_status_basis"] = _version_status(rp, curated)

    # An unsmudged LFS pointer is not the document. Recording the stub's hash
    # would put a 131-byte placeholder's identity where the source's belongs,
    # and every consumer that gates on sha256 -- ingestion, publish -- would
    # then treat it as real content. Leave sha256 null, the way an
    # absent-from-disk row does, and say why.
    if is_lfs_pointer(path):
        ptr = lfs_pointer_info(path) or {}
        rec["sha256"] = None
        rec["file_size_bytes"] = stat.st_size
        rec["lfs_pointer"] = True
        rec["lfs_declared_sha256"] = ptr.get("oid")
        rec["lfs_declared_size_bytes"] = ptr.get("size")
        rec["extraction_method"] = "not-fetched"
        rec["processing_state"] = "not-fetched"
        rec["inspection_notes"].append(
            "unsmudged Git LFS pointer, not document content; "
            f"fetch the bytes with `{FETCH_HINT}`")
        return rec

    if suffix in PDF_SUFFIXES:
        info = _pdfinfo(path)
        try:
            pages = int(info.get("Pages", "0"))
        except ValueError:
            pages = 0
        rec["page_count"] = pages
        rec["pdf_producer"] = info.get("Producer")
        rec["pdf_creator"] = info.get("Creator")
        rec["pdf_creation_date"] = info.get("CreationDate")
        rec["pdf_encrypted"] = info.get("Encrypted", "no")
        rec["pdf_page_size"] = info.get("Page size")
        if pages:
            counts = _page_char_counts(path, pages)
            total = sum(counts)
            rec["text_chars_per_page"] = counts
            rec["text_chars_total"] = total
            rec["pages_with_text"] = sum(1 for c in counts if c >= TEXT_LAYER_MIN_CHARS)
            rec["text_layer_available"] = rec["pages_with_text"] > 0
            per_page = total / pages
            rec["suspected_scan"] = per_page < SCAN_CHARS_PER_PAGE
            if rec["suspected_scan"]:
                rec["extraction_method"] = "pdftoppm+tesseract-ocr"
            elif rec["pages_with_text"] < pages:
                rec["extraction_method"] = "pdftotext-bbox+ocr-for-empty-pages"
            else:
                rec["extraction_method"] = "pdftotext-bbox"
        else:
            rec["inspection_notes"].append("pdfinfo reported 0 pages")
            rec["extraction_method"] = "unreadable"
    elif suffix in IMAGE_SUFFIXES:
        rec["page_count"] = 1
        rec["text_layer_available"] = False
        rec["suspected_scan"] = True
        rec["extraction_method"] = "tesseract-ocr"
    elif suffix in DOCX_SUFFIXES:
        rec["page_count"] = None
        rec["text_layer_available"] = True
        rec["suspected_scan"] = False
        rec["extraction_method"] = "docx-xml"
    else:
        rec["extraction_method"] = "unsupported"
        rec["inspection_notes"].append(f"unsupported file type {suffix!r}")
    return rec


def build_manifest(workers: int = 8) -> list[dict]:
    curated = _load_curated_metadata()
    files: list[Path] = []
    for root in CORPUS_ROOTS:
        files.extend(p for p in sorted(root.rglob("*")) if p.is_file())

    tasks = [(str(p), curated.get(rel(p), {})) for p in files]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(inspect_file, tasks, chunksize=1))

    # Curated index entries whose file is absent from disk are recorded too, so
    # coverage reporting can tell "not on disk" from "never indexed".
    on_disk = {r["source_path"] for r in records}
    for lp, row in sorted(curated.items()):
        if lp not in on_disk:
            records.append({
                "doc_id": doc_id_for(lp),
                "source_path": lp,
                "sha256": None,
                "file_type": Path(lp).suffix.lstrip("."),
                "manufacturer": row.get("manufacturer"),
                "doc_type": row.get("doc_type"),
                "title": row.get("title"),
                "source_url": row.get("url"),
                "in_curated_index": True,
                "processing_state": "absent-from-disk",
                "inspection_notes": ["referenced by a documents-index entry but not on disk"],
            })

    records.sort(key=lambda r: r["source_path"])
    generated = datetime.now(timezone.utc).isoformat()
    with open_write(MANIFEST_PATH) as f:
        for r in records:
            r["manifest_generated_at"] = generated
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return records


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    recs = build_manifest()
    pdfs = [r for r in recs if r.get("file_type") == "pdf" and r.get("sha256")]
    print(f"files inspected      : {sum(1 for r in recs if r.get('sha256'))}")
    print(f"  pdfs               : {len(pdfs)}")
    print(f"  with text layer    : {sum(1 for r in pdfs if r.get('text_layer_available'))}")
    print(f"  suspected scans    : {sum(1 for r in pdfs if r.get('suspected_scan'))}")
    print(f"  total pages        : {sum(r.get('page_count') or 0 for r in pdfs)}")
    print(f"absent from disk     : {sum(1 for r in recs if r['processing_state'] == 'absent-from-disk')}")
    n_unfetched = sum(1 for r in recs if r['processing_state'] == 'not-fetched')
    print(f"not fetched (pointer): {n_unfetched}")
    if n_unfetched:
        print(f"  -> {n_unfetched} file(s) are unsmudged Git LFS pointers, not "
              f"documents; fetch them with `{FETCH_HINT}`")
    print(f"wrote {MANIFEST_PATH}")
