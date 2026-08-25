"""The hand-researched dataset, treated as what it is: a source, not a spine.

`data/*.json` and `data/structural/*.json` describe **products** — 32 product
lines, 59 assemblies, 225 components — where the evidence store describes
**documents**. It has close to the shape the contract's structural types want and
it carries **no provenance at all**: a `sub_assembly` has ten keys and not one of
them names a document, page, element or bounding box.

That is why this module baselines it rather than reading it. Three measurements
decide the treatment:

* **Its only accuracy measurement is 4 contradicted claims in 30 checked** —
  13.3%, and 25% in the one file the rest of the corpus leans on most
  (`docs/state-and-gaps.md` G16). The 225 components have **no** accuracy
  measurement of any kind; the 13.3% is from the other half.
* **211 of 225 `component_id` values appear nowhere in the corpus.** Published as
  `Part.id`, the primary key of the entity layer would be uncited by construction.
* **Roughly 12-25% of its values could never be anchored** to any corpus
  document — resin chemistry, UV-inhibitor loading, marketing claims. `impact
  modifier` and `PHR` have zero hits across all 81,794 elements.

The repository already grades it accordingly: `docs/curation/` ranks
`curated_dataset` at **authority 20 of 100**, above only `inferred`, and states
that evidence of that kind *"can never reach `accepted`"*.

**But its composition graph is not in the same category.** Invariant 10 of the
data model is explicit: *"Structure is authored, not extracted. No table reader
produces a `PanelSpec`."* No amount of curation over 2,147 pages will establish
that three particular components compose one Chesterfield panel. Somebody
authored that, 59 times, and it cannot be re-derived from evidence.

So: **the values are curated like any other source; the structure is authored.**
See `docs/layering.md` §5.
"""
from __future__ import annotations

import json
from pathlib import Path

from .ids import sha256_file
from .paths import CATALOG_DIR, REPO_ROOT, open_write

DIGEST_PATH = CATALOG_DIR / "data-digests.json"

# `master-dataset.json` and the two `*documents-index.json` files are OUTPUT of
# scripts/build_master.py, which is idempotent and safe to re-run. Baselining
# generated artifacts would flag every legitimate rebuild as tampering.
_GENERATED = ("master-dataset.json", "documents-index.json",
              "china-documents-index.json")

WHY = ("A baseline of the hand-researched dataset before any curation phase "
       "touches it. `data/` has one commit in its history and carries four "
       "claims contradicted by their own sources (state-and-gaps G16), which "
       "are still present verbatim because correcting someone's research is "
       "their call. If a value is ever silently amended, this is what makes the "
       "change visible rather than invisible. Acceptance criterion P1b.")


class DatasetChanged(RuntimeError):
    """The dataset no longer matches its baseline.

    Not necessarily wrong -- a researcher correcting G16's four errors would
    raise this, and that is a good day. It means somebody must look and then
    re-baseline deliberately, rather than the change passing unnoticed.
    """


def _files() -> list[Path]:
    roots = [REPO_ROOT / "data", REPO_ROOT / "china" / "data"]
    out = []
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.json")):
            if p.name in _GENERATED:
                continue
            out.append(p)
    # Globally sorted, not per-root: the baseline is read as a diff, and a stable
    # global order keeps an added file next to its neighbours.
    return sorted(out, key=lambda p: str(p.relative_to(REPO_ROOT)))


def digest_dataset() -> dict:
    """SHA-256 every hand-maintained dataset file, keyed by repo-relative path."""
    return {
        "why": WHY,
        "files": {str(p.relative_to(REPO_ROOT)): {"sha256": sha256_file(p),
                                                  "bytes": p.stat().st_size}
                  for p in _files()},
    }


def write_digests() -> Path:
    payload = digest_dataset()
    DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open_write(DIGEST_PATH) as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return DIGEST_PATH


def load_digests() -> dict:
    return json.loads(DIGEST_PATH.read_text())


def verify_dataset(baseline: dict | None = None) -> dict:
    """Compare the tree to the baseline. Raises on any difference."""
    base = (baseline or load_digests())["files"]
    now = digest_dataset()["files"]
    problems = []
    for path, meta in sorted(base.items()):
        if path not in now:
            problems.append(f"{path}: missing — it is in the baseline and not on disk")
        elif now[path]["sha256"] != meta["sha256"]:
            problems.append(f"{path}: changed — {meta['sha256'][:12]}… → "
                            f"{now[path]['sha256'][:12]}…")
    for path in sorted(set(now) - set(base)):
        problems.append(f"{path}: not in the baseline — a dataset file was added")
    if problems:
        raise DatasetChanged(
            f"{len(problems)} difference(s) against {DIGEST_PATH.name}. This is not "
            f"automatically wrong — a researcher correcting G16's four errors would "
            f"land here — but somebody must look, and then re-baseline deliberately:"
            f"\n  - " + "\n  - ".join(problems))
    return {"files": len(now), "unchanged": True}
