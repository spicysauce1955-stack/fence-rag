"""Machine reader for material-list (kit/BOM) tables already in the store.

The corpus holds complete per-configuration kit lists ingested as canonical
`table` elements with real `table_cells` — the Weatherables CAD pages
(Augusta, Pembroke) and the Catalyst SKU sheets (Cape Cod, accents/hardware,
Madison) among them: `[measured]` 45 BOM-shaped tables across 5 documents.
None of them are in `table_read_candidates`, because that lifecycle is loaded
from agent-read files and no agent has read these tables.

This script bridges the two WITHOUT inventing a parallel store: it emits the
exact JSON shape `table_review.load_reading()` already ingests (the
`agent-read-*.json` contract), with `reader_kind` distinguishing machine
readings from agent readings, and prints the load command. Each ROW of a kit
table becomes one candidate row (row_label = the ITEM cell), so review is
row-granular — a kit row (component + qty + dimensions) is the judgement a
reviewer actually makes — instead of cell-granular.

What this is NOT: it does not promote, publish or classify anything. Facts
still come only through the review lifecycle; composition stays authored
(Invariant 10: no table reader produces a PanelSpec).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fence_evidence.paths import REPO_ROOT  # noqa: E402

OUT = ROOT / 'workspace/tests/machine-read-kit-tables.json'
READER = 'machine-kit-tables-v1'

# A kit/BOM table: a QTY-ish header plus an item-ish header, and at least
# three data rows carrying numbers. Deliberately permissive on header
# spelling (QTY | QUANTITY | ITEM | PART | DESCRIPTION | DIMENSION(S)) —
# the reader only proposes candidates; a human still reviews.
QTY_HEADERS = re.compile(r"^(qty|quantity|count)$", re.I)
ITEM_HEADERS = re.compile(r"^(item|part|component|description)$", re.I)
MIN_DATA_ROWS = 3


def _cells(conn: sqlite3.Connection, element_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT tc.row, tc.col, tc.text FROM table_cells tc
             JOIN tables t ON tc.table_id = t.table_id
            WHERE t.element_id = ?
           ORDER BY tc.row, tc.col""", (element_id,)).fetchall()
    grid: dict[int, dict[int, str]] = {}
    for r in rows:
        grid.setdefault(r['row'], {})[r['col']] = (r['text'] or '').strip()
    return [grid[n] for n in sorted(grid)]


def _is_kit_table(grid: list[dict]) -> tuple[bool, dict[str, int] | None]:
    """(is_kit, header_map) — header_map names the qty/item/dimension columns."""
    if not grid:
        return False, None
    header = grid[0]
    qty = item = dim = None
    for col, text in header.items():
        if QTY_HEADERS.fullmatch(text):
            qty = col
        elif ITEM_HEADERS.fullmatch(text):
            item = col
        elif re.fullmatch(r"dimension(s)?", text, re.I):
            dim = col
    # Gate lists (Socket Posts / Post Cap) also match; so do rail/picket
    # rows. The shape test is the headers, not the item names.
    if qty is None or item is None:
        return False, None
    data = [row for row in grid[1:] if row]
    # At least MIN_DATA_ROWS rows with a quantity that parses as a number.
    numeric = 0
    for row in data:
        value = row.get(qty, '')
        if re.fullmatch(r"\d+", value):
            numeric += 1
    if numeric < MIN_DATA_ROWS:
        return False, None
    return True, {'qty': qty, 'item': item, 'dim': dim}


def main() -> int:
    conn = sqlite3.connect(f"file:{REPO_ROOT / 'workspace/indexes/evidence.db'}?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    elements = conn.execute(
        """SELECT e.element_id, e.document_id, e.page_no, d.source_path
             FROM elements e JOIN documents d ON e.document_id = d.document_id
            WHERE e.element_type = 'table'""").fetchall()
    pages, found = [], 0
    by_document: dict[str, int] = {}
    for el in elements:
        grid = _cells(conn, el['element_id'])
        is_kit, headers = _is_kit_table(grid)
        if not is_kit:
            continue
        found += 1
        by_document[el['source_path'].split('/')[-1]] = \
            by_document.get(el['source_path'].split('/')[-1], 0) + 1
        rows = []
        for row in grid[1:]:
            if not row:
                continue
            cells = [row.get(c, '') for c in sorted(row)]
            # Normalize the column order to the header map so the reading's
            # grid matches the page's own semantics, not the layout's column
            # order: a reviewer sees ITEM | QTY | DIMENSIONS consistently.
            item = row.get(headers['item'], '')
            qty = row.get(headers['qty'], '')
            dim = row.get(headers['dim'], '') if headers['dim'] is not None else ''
            rows.append({'cells': [item, qty, dim] if headers['dim'] is not None
                         else [item, qty]})
        pages.append({
            'source_path': el['source_path'],
            'page_no': el['page_no'],
            'reader': READER,
            'is_table': True,
            'table_kind': 'kit_material_list',
            'what_the_page_is': (
                'Material list read mechanically from the canonical table element '
                + el['element_id']
                + ' (cells from the extraction layer; no crop rendered).'),
            'grid': {'headers': (['ITEM', 'QTY', 'DIMENSIONS']
                                 if headers['dim'] is not None else ['ITEM', 'QTY']),
                     'rows': rows},
            'reading_confidence': 'machine:canonical_cells',
            'notes': ('Mechanical reading of canonical table_cells for element '
                      + el['element_id'] + '; row-granular review (one candidate row '
                      'per kit line, row_label = ITEM cell).'),
        })
    conn.close()
    payload = {'pages': pages}
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'kit_tables_found': found,
                      'by_document': by_document,
                      'output': str(OUT.relative_to(ROOT)),
                      'load_command': 'python3 -m fence_evidence.cli table-review '
                                      '--load-dir workspace/tests --pattern '
                                      'machine-read-kit-tables.json'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())