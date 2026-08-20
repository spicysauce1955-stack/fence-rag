#!/usr/bin/env python3
"""Merge china/data/*.json into a standalone China dataset + document index.
Kept fully separate from master-dataset.json (US/Western manufacturers) per user request.
"""
import json
import os
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHINA_DIR = os.path.join(BASE, "china")
CHINA_DATA_DIR = os.path.join(CHINA_DIR, "data")


def normalize_doc(doc, fallback_manufacturer):
    doc = dict(doc)
    local_path = doc.get("local_path") or doc.get("local_file") or doc.get("file")
    url = doc.get("url") or doc.get("source_url") or doc.get("source_image") or doc.get("source_page")
    title = doc.get("title") or doc.get("title_en") or doc.get("description")
    return {
        "manufacturer": doc.get("manufacturer", fallback_manufacturer),
        "doc_type": doc.get("doc_type") or "unspecified",
        "title": title,
        "title_zh": doc.get("title_zh"),
        "model_or_line": doc.get("model_or_line"),
        "date_or_version": doc.get("date_or_version"),
        "url": url,
        "local_path": local_path,
    }


with open(os.path.join(CHINA_DATA_DIR, "china-manufacturers.json")) as f:
    manufacturers_data = json.load(f)

with open(os.path.join(CHINA_DATA_DIR, "china-installation-technical.json")) as f:
    installation_data = json.load(f)

all_documents = []
for m in manufacturers_data.get("manufacturers", []) or []:
    for doc in m.get("documents", []) or []:
        all_documents.append(normalize_doc(doc, m.get("manufacturer") or m.get("name")))
for doc in installation_data.get("documents", []) or []:
    all_documents.append(normalize_doc(doc, "Cross-manufacturer / installation-technical"))

china_dataset = {
    "region": "China",
    "note": "Separate track from master-dataset.json (US/Western manufacturers) — kept apart per explicit request. Source language: zh (Chinese) unless noted; unit system: metric (mm) with inch-equivalents noted where the source provided them.",
    "manufacturers_and_gb_standards": manufacturers_data,
    "installation_and_technical": installation_data,
}

china_dataset_path = os.path.join(CHINA_DIR, "china-dataset.json")
with open(china_dataset_path, "w") as f:
    json.dump(china_dataset, f, indent=2, ensure_ascii=False)

# --- Document index, cross-checked against files on disk ---
on_disk = set()
for path in glob.glob(os.path.join(CHINA_DIR, "manuals", "**", "*"), recursive=True):
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
    row = dict(doc)
    row["local_path"] = rel
    row["file_exists"] = exists
    index_rows.append(row)

orphan_files = sorted(on_disk - indexed_paths)

index_path = os.path.join(CHINA_DATA_DIR, "china-documents-index.json")
with open(index_path, "w") as f:
    json.dump({
        "total_indexed_documents": len(index_rows),
        "documents_with_verified_local_file": sum(1 for r in index_rows if r["file_exists"]),
        "documents_missing_local_file": sum(1 for r in index_rows if r["local_path"] and not r["file_exists"]),
        "documents_url_only_no_download": sum(1 for r in index_rows if not r["local_path"]),
        "files_on_disk_not_in_index": orphan_files,
        "documents": index_rows,
    }, f, indent=2, ensure_ascii=False)

print(f"China manufacturers: {len(manufacturers_data.get('manufacturers', []) or [])}")
print(f"GB standards entries: {len(manufacturers_data.get('gb_standards', []) or [])}")
print(f"Total document entries indexed: {len(index_rows)}")
print(f"Verified on disk: {sum(1 for r in index_rows if r['file_exists'])}")
print(f"Missing (broken local_path): {sum(1 for r in index_rows if r['local_path'] and not r['file_exists'])}")
print(f"URL-only (no download): {sum(1 for r in index_rows if not r['local_path'])}")
print(f"Files on disk but NOT referenced: {len(orphan_files)}")
for o in orphan_files:
    print("  ORPHAN:", o)
print(f"\nWrote {china_dataset_path}")
print(f"Wrote {index_path}")
