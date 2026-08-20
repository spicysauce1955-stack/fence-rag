#!/usr/bin/env python3
"""Merge per-manufacturer data/*.json into a master dataset + PDF document index."""
import json
import os
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
MANUFACTURER_FILES = [
    "certainteed-bufftech.json",
    "freedom-outdoor-living.json",
    "illusions-vinyl-fence.json",
    "barrette-outdoor-living.json",
    "weatherables.json",
    "wam-bam.json",
]
STANDARDS_FILE = "industry-standards.json"

manufacturers = []
all_documents = []


def normalize_doc(doc, fallback_manufacturer):
    doc = dict(doc)
    local_path = doc.get("local_path") or doc.get("local_file") or doc.get("file")
    url = doc.get("url") or doc.get("source_url") or doc.get("source_image") or doc.get("source_page")
    title = doc.get("title") or doc.get("description")
    return {
        "manufacturer": doc.get("manufacturer", fallback_manufacturer),
        "doc_type": doc.get("doc_type") or "unspecified",
        "title": title,
        "model_or_line": doc.get("model_or_line"),
        "date_or_version": doc.get("date_or_version"),
        "url": url,
        "local_path": local_path,
    }

STRUCTURAL_DIR = os.path.join(DATA_DIR, "structural")
STRUCTURAL_SUPPLEMENT_MAP = {
    "certainteed-bufftech.json": "certainteed-bufftech-structural.json",
    "freedom-outdoor-living.json": "freedom-outdoor-living-structural.json",
    "illusions-vinyl-fence.json": "illusions-vinyl-fence-structural.json",
    "barrette-outdoor-living.json": "barrette-outdoor-living-structural.json",
    "weatherables.json": "weatherables-structural.json",
    "wam-bam.json": "wam-bam-structural.json",
}

for fname in MANUFACTURER_FILES:
    path = os.path.join(DATA_DIR, fname)
    with open(path) as f:
        d = json.load(f)

    supplement_fname = STRUCTURAL_SUPPLEMENT_MAP.get(fname)
    supplement_path = os.path.join(STRUCTURAL_DIR, supplement_fname) if supplement_fname else None
    if supplement_path and os.path.isfile(supplement_path):
        with open(supplement_path) as f:
            supplement = json.load(f)
        d["structural_supplement"] = supplement
        for doc in supplement.get("documents", []):
            all_documents.append(normalize_doc(doc, d.get("manufacturer")))

    manufacturers.append(d)
    for doc in d.get("documents", []):
        all_documents.append(normalize_doc(doc, d.get("manufacturer")))

with open(os.path.join(DATA_DIR, STANDARDS_FILE)) as f:
    standards = json.load(f)
    for doc in standards.get("documents", []):
        all_documents.append(normalize_doc(doc, "Industry Standards / Cross-Manufacturer"))

standards_supplement_path = os.path.join(STRUCTURAL_DIR, "industry-standards-structural.json")
if os.path.isfile(standards_supplement_path):
    with open(standards_supplement_path) as f:
        standards_supplement = json.load(f)
    standards["structural_supplement"] = standards_supplement
    for doc in standards_supplement.get("documents", []):
        all_documents.append(normalize_doc(doc, "Industry Standards / Cross-Manufacturer"))

master = {
    "schema": "../schema/bom-schema.json",
    "manufacturers": manufacturers,
    "industry_standards": standards,
}

master_path = os.path.join(BASE, "master-dataset.json")
with open(master_path, "w") as f:
    json.dump(master, f, indent=2)

# --- Document index: cross-check against files actually on disk ---
on_disk = set()
for path in glob.glob(os.path.join(BASE, "manuals", "**", "*"), recursive=True):
    if os.path.isfile(path):
        on_disk.add(os.path.relpath(path, BASE))

indexed_paths = set()
index_rows = []
for doc in all_documents:
    local_path = doc.get("local_path")
    rel = None
    exists = False
    if local_path:
        rel = os.path.relpath(local_path, BASE) if os.path.isabs(local_path) else local_path
        exists = os.path.isfile(os.path.join(BASE, rel)) if rel else False
        if exists:
            indexed_paths.add(rel)
    index_rows.append({
        "manufacturer": doc.get("manufacturer"),
        "doc_type": doc.get("doc_type"),
        "title": doc.get("title"),
        "model_or_line": doc.get("model_or_line"),
        "date_or_version": doc.get("date_or_version"),
        "url": doc.get("url"),
        "local_path": rel,
        "file_exists": exists,
    })

orphan_files = sorted(on_disk - indexed_paths)

index_path = os.path.join(BASE, "data", "documents-index.json")
with open(index_path, "w") as f:
    json.dump({
        "total_indexed_documents": len(index_rows),
        "documents_with_verified_local_file": sum(1 for r in index_rows if r["file_exists"]),
        "documents_missing_local_file": sum(1 for r in index_rows if r["local_path"] and not r["file_exists"]),
        "documents_url_only_no_download": sum(1 for r in index_rows if not r["local_path"]),
        "files_on_disk_not_in_index": orphan_files,
        "documents": index_rows,
    }, f, indent=2)

print(f"Manufacturers merged: {len(manufacturers)}")
print(f"Total document entries indexed: {len(index_rows)}")
print(f"Verified on disk: {sum(1 for r in index_rows if r['file_exists'])}")
print(f"Missing (broken local_path): {sum(1 for r in index_rows if r['local_path'] and not r['file_exists'])}")
print(f"URL-only (no download): {sum(1 for r in index_rows if not r['local_path'])}")
print(f"Files on disk but NOT referenced in any documents[] entry: {len(orphan_files)}")
for o in orphan_files:
    print("  ORPHAN:", o)
print(f"\nWrote {master_path}")
print(f"Wrote {index_path}")
