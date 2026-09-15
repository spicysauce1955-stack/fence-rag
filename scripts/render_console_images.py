"""Render the page images the review console inlines.

Separate from the console builder because rendering shells out to poppler and
takes a few seconds, while the console itself regenerates instantly from the
store. Writes JPEGs at 90 dpi -- enough to read a footing table, small enough
that a sitting's worth fits in an Artifact with room to spare (the PNG crops the
store already holds come to 19 MB).

Two queues need images, for the same reason: **a reviewer who cannot see the
page cannot decide.** The table loop needs the crop; the step loop needs the
whole page, because whether a bullet is an `AssemblyStep` or a rationale is
often only decidable from the layout around it. The step side used to be one
hard-coded page, so a reviewer who moved to any other page got no image at all.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "workspace/derived/console-img"
# G79: the disputed page beside the sibling built from the same drawing template.
G79 = [("manuals/certainteed-bufftech/structural/"
        "NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf", 11, "g79-disputed"),
       ("manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-"
        "Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf",
        17, "g79-sibling")]


def connect(db=None) -> sqlite3.Connection:
    db = db or ROOT / "workspace/indexes/evidence.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def step_jobs(conn, document_id=None) -> list[tuple]:
    """`(source_path, page_no, name)` for every page with an undecided step
    candidate on it — the pages a sitting can be worked against.

    Narrowable to one document: sixty pages of poppler to review one page is a
    reason not to run it at all.
    """
    where, params = "", []
    if document_id is not None:
        where, params = "AND c.document_id = ?", [document_id]
    rows = conn.execute(f"""
        SELECT DISTINCT c.document_id, c.page_no, d.source_path
          FROM step_candidates c
          JOIN documents d ON d.document_id = c.document_id
         WHERE c.review_status = 'unreviewed' {where}
         ORDER BY d.source_path, c.page_no""", params).fetchall()
    return [(r["source_path"], r["page_no"],
             f"step-{r['document_id']}-p{r['page_no']}") for r in rows]


def crop_jobs(conn) -> list[tuple]:
    """One page image per crop still waiting for a table review."""
    jobs, seen = [], set()
    for r in conn.execute("""SELECT DISTINCT t.crop_path, d.source_path, t.page_no
                               FROM table_read_candidates t
                               JOIN documents d ON d.document_id = t.document_id
                              WHERE t.review_status = 'unreviewed'"""):
        key = r["crop_path"].rsplit("/", 1)[-1].split("-")[0]
        if key in seen:
            continue
        seen.add(key)
        jobs.append((r["source_path"], r["page_no"], f"crop-{key}"))
    return jobs


def render(src, page, name, out_dir, dpi=90, quality=55) -> None:
    subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", f"quality={quality}",
                    "-f", str(page), "-l", str(page), "-r", str(dpi),
                    "-singlefile", str(ROOT / src), str(out_dir / name)],
                   check=True, capture_output=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--document", help="only this document's step pages")
    ap.add_argument("--skip-existing", action="store_true",
                    help="leave images already rendered alone")
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)

    out_dir = OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    jobs = step_jobs(conn, args.document) + crop_jobs(conn) + G79
    done = 0
    for src, page, name in jobs:
        if args.skip_existing and (out_dir / f"{name}.jpg").is_file():
            continue
        try:
            render(src, page, name, out_dir)
            done += 1
        except Exception as exc:              # a missing PDF is not fatal
            print(f"skip {name}: {str(exc)[:70]}")
    total = sum(f.stat().st_size for f in out_dir.glob("*.jpg"))
    print(f"rendered {done} of {len(jobs)}; {len(list(out_dir.glob('*.jpg')))} "
          f"images, {total / 1024 / 1024:.2f} MB -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
