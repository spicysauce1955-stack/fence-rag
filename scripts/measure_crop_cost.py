"""K3 — what does a cold paragraph crop cost?

A benchmark, not a dataset builder: it reads the store and the corpus and is safe
to re-run. (The two `build_*.py` scripts beside it own their outputs; this one has
none.) One caveat since `SCHEMA_VERSION` 2: `store.connect()` applies any pending
additive migration, so on an out-of-date store this is not strictly read-only. Results as of 2026-08-25 are in
`workspace/reports/k3-crop-render-cost.md`.

source-refs-design.md §8.4: "§4.2 chooses poppler windowing over cached Pillow
crops on correctness and dependency grounds without knowing what a cold
paragraph crop costs. That number should exist before a queue is built on it."

Measures the real code path (fence_evidence.crops.render_crop), not a shell
approximation. Reports per-stratum distributions, because the question a review
queue actually asks is "what does a screen of 50 rows cost", and that depends on
which documents those rows land in.
"""
import json
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fence_evidence.crops import CropError, render_crop
from fence_evidence.paths import REPO_ROOT
from fence_evidence.store import connect

SEED = 20260825
N_PER_STRATUM = 40


def page_count(pdf: Path) -> int:
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, timeout=30)
        for line in out.stdout.decode("utf-8", "replace").splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0


def main():
    random.seed(SEED)
    conn = connect()
    rows = conn.execute("""
        SELECT e.element_id, e.bbox, e.page_no, e.element_type,
               p.width, p.height, p.page_image_dpi, p.has_text_layer,
               d.source_path, d.document_id
          FROM elements e
          JOIN pages p ON p.page_id = e.page_id
          JOIN documents d ON d.document_id = e.document_id
         WHERE e.bbox IS NOT NULL
           AND p.page_image_dpi IS NOT NULL
           AND d.source_path LIKE '%.pdf'
    """).fetchall()
    conn.close()
    print(f"boxed elements available: {len(rows)}", file=sys.stderr)

    # file size and page count per document, measured once
    docs = {}
    for r in rows:
        if r["document_id"] in docs:
            continue
        p = REPO_ROOT / r["source_path"]
        if not p.is_file():
            continue
        docs[r["document_id"]] = {"bytes": p.stat().st_size, "pages": page_count(p)}
    print(f"documents: {len(docs)}", file=sys.stderr)

    def stratum(r):
        d = docs.get(r["document_id"])
        if not d:
            return None
        mb = d["bytes"] / 1e6
        size = "small (<1MB)" if mb < 1 else "medium (1-5MB)" if mb < 5 else "large (>5MB)"
        layer = "text-layer" if r["has_text_layer"] else "scanned"
        return f"{size} / {layer}"

    buckets = defaultdict(list)
    for r in rows:
        s = stratum(r)
        if s:
            buckets[s].append(r)

    results = defaultdict(list)
    failures = defaultdict(int)
    seen_docs = set()
    cold_first_touch = []

    for name, pool in sorted(buckets.items()):
        sample = random.sample(pool, min(N_PER_STRATUM, len(pool)))
        for r in sample:
            bbox = json.loads(r["bbox"])
            t0 = time.perf_counter()
            try:
                out = render_crop(r["source_path"], r["page_no"], bbox,
                                  page_w_pt=r["width"], page_h_pt=r["height"],
                                  dpi=r["page_image_dpi"])
            except CropError as exc:
                failures[f"{name}: {str(exc)[:60]}"] += 1
                continue
            dt = (time.perf_counter() - t0) * 1000
            results[name].append(dt)
            first = r["document_id"] not in seen_docs
            seen_docs.add(r["document_id"])
            if first:
                cold_first_touch.append(dt)
            try:
                out.unlink()
                out.parent.rmdir()
            except Exception:
                pass

    def stats(xs):
        if not xs:
            return None
        xs = sorted(xs)
        return {
            "n": len(xs),
            "p50": round(statistics.median(xs), 1),
            "p95": round(xs[int(len(xs) * 0.95)] if len(xs) > 1 else xs[0], 1),
            "max": round(xs[-1], 1),
            "mean": round(statistics.mean(xs), 1),
        }

    report = {
        "seed": SEED,
        "by_stratum": {k: stats(v) for k, v in sorted(results.items())},
        "all": stats([x for v in results.values() for x in v]),
        "first_touch_per_document": stats(cold_first_touch),
        "failures": dict(failures),
    }

    # page-count correlation: does seeking to a late page cost more?
    by_page = defaultdict(list)
    for name, pool in sorted(buckets.items()):
        for r in random.sample(pool, min(30, len(pool))):
            d = docs.get(r["document_id"])
            if not d or not d["pages"]:
                continue
            bbox = json.loads(r["bbox"])
            t0 = time.perf_counter()
            try:
                out = render_crop(r["source_path"], r["page_no"], bbox,
                                  page_w_pt=r["width"], page_h_pt=r["height"],
                                  dpi=r["page_image_dpi"])
            except CropError:
                continue
            dt = (time.perf_counter() - t0) * 1000
            bucket = ("page 1-5" if r["page_no"] <= 5 else
                      "page 6-25" if r["page_no"] <= 25 else "page 26+")
            by_page[bucket].append(dt)
            try:
                out.unlink(); out.parent.rmdir()
            except Exception:
                pass
    report["by_page_position"] = {k: stats(v) for k, v in sorted(by_page.items())}

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
