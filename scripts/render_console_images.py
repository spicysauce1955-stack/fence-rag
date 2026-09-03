"""Render the page images the review console inlines.

Separate from the console builder because rendering shells out to poppler and
takes a few seconds, while the console itself regenerates instantly from the
store. Writes JPEGs at 90 dpi -- enough to read a footing table, small enough
that all sixteen fit in an Artifact with room to spare (2.3 MB against a 16 MB
ceiling; the PNG crops the store already holds come to 19 MB).
"""
import pathlib
import sqlite3
import subprocess

ROOT = pathlib.Path.cwd()
OUT = ROOT / "workspace/derived/console-img"
OUT.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(f"file:{ROOT}/workspace/indexes/evidence.db?mode=ro", uri=True)
conn.row_factory = sqlite3.Row


def render(src, page, name, dpi=90, quality=55):
    subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", f"quality={quality}",
                    "-f", str(page), "-l", str(page), "-r", str(dpi),
                    "-singlefile", str(ROOT / src), str(OUT / name)],
                   check=True, capture_output=True)


jobs = [("manuals/certainteed-bufftech/bufftech-fence-installation-guide-2024.pdf",
         8, "slice-p8")]
seen = set()
for r in conn.execute("""SELECT DISTINCT t.crop_path, d.source_path, t.page_no
                           FROM table_read_candidates t
                           JOIN documents d ON d.document_id = t.document_id
                          WHERE t.review_status = 'unreviewed'"""):
    key = r["crop_path"].rsplit("/", 1)[-1].split("-")[0]
    if key in seen:
        continue
    seen.add(key)
    jobs.append((r["source_path"], r["page_no"], f"crop-{key}"))
# G79: the disputed page beside the sibling built from the same drawing template
jobs += [("manuals/certainteed-bufftech/structural/"
          "NOA-12-1106.11-extruded-pvc-vinyl-fencing.pdf", 11, "g79-disputed"),
         ("manuals/certainteed-bufftech/structural/NOA-23-0314.05-CertainTeed-"
          "Chesterfield-Columbia-Imperial-Breezewood-Brookline-current-2023-2029.pdf",
          17, "g79-sibling")]

for src, page, name in jobs:
    try:
        render(src, page, name)
    except Exception as exc:                      # a missing PDF is not fatal
        print(f"skip {name}: {str(exc)[:70]}")
total = sum(f.stat().st_size for f in OUT.glob("*.jpg"))
print(f"{len(list(OUT.glob('*.jpg')))} images, {total/1024/1024:.2f} MB -> {OUT}")
