"""The Discovery read model behind `GET /source-refs/{id}`. No HTTP.

One function assembles the §5.1 wire shape for one ref; one assembles it for a
batch under a deadline. `api.py` is routing and error mapping around these two
and holds no logic of its own (D5).

```json
{ "id": "eb2c863494b90243", "belongs_to": "<content_hash>", "page_no": 47,
  "text": "Call before you dig.",
  "image": {"url": "crops/eb/eb2c863494b90243-200-64e1ee02ac41867f.png",
            "sha256": "...", "dpi": 200},
  "warnings": [{"code": "SOURCE_TEXT_FROM_OCR", "params": {"confidence": 95.6}}] }
```

Four readings this module makes, all of which could have gone the other way:

**`belongs_to` is a content hash, so warnings are unioned over every filing of
those bytes.** 14 groups of byte-identical files are filed under different
manufacturers and are never deduplicated. A ref names the *bytes*; asking
"which document is this?" has no single answer, and picking one filing would
make a warning appear or vanish depending on an alphabetical tie-break. Only
the *rendering* picks a filing, and only because it needs one path -- the
bytes are identical, so the picture is not a choice.

**`text` is null unless the ref resolves to exactly one element.** `ref_id`
omits `kind` and is not injective: 9,929 ids cover more than one element, and
`refs.Locus` deliberately refuses to pick between them. Concatenating them
would invent a quote that appears nowhere; picking the first would attribute
the wrong one to a citation. Null is the honest answer and the caller still
has the image, which is the evidence anyway.

**A ref with no image is still a ref.** `source_ref` raises only when the id
names nothing. A ref that resolves but cannot be pictured -- a page ref, the
DOCX, a CAD PNG, an unfetched checkout -- comes back with `image: null` and a
warning saying which, because a 404 on a citation that *does* resolve would
contradict the guarantee obligation 3 makes about it.

**Warning codes are `SOURCE_*` from `registry-additions.md` §2 and nothing
else.** Errors live in an `error.*` namespace (§5.2 of the design, defect 5):
Planning's `test_locale_bundles.py` fails their build on any registry code
lacking both locale bundles, so an HTTP failure smuggled in here as a warning
would break their CI rather than ours.
"""
from __future__ import annotations

import sqlite3
import time

from . import refs
from .cropcache import CropUnavailable, ensure_crop, relative_url
from .paths import REPO_ROOT, is_lfs_pointer
from .tenancy import visible_sql

# registry-additions.md §2. Named rather than inlined so a test can assert the
# set this module can emit is a subset of the registry's ten.
SOURCE_TEXT_FROM_OCR = "SOURCE_TEXT_FROM_OCR"
SOURCE_OCR_LOW_CONFIDENCE = "SOURCE_OCR_LOW_CONFIDENCE"
SOURCE_TEXT_LAYER_MOJIBAKE = "SOURCE_TEXT_LAYER_MOJIBAKE"
SOURCE_TABLE_NOT_RECONSTRUCTED = "SOURCE_TABLE_NOT_RECONSTRUCTED"
SOURCE_DOCUMENT_SUPERSEDED = "SOURCE_DOCUMENT_SUPERSEDED"
SOURCE_VERSION_STATUS_UNKNOWN = "SOURCE_VERSION_STATUS_UNKNOWN"
SOURCE_STATUS_BASIS_FILENAME = "SOURCE_STATUS_BASIS_FILENAME"
SOURCE_CONTENT_DUPLICATED = "SOURCE_CONTENT_DUPLICATED"
SOURCE_NO_IMAGE_AVAILABLE = "SOURCE_NO_IMAGE_AVAILABLE"
SOURCE_NOT_FETCHED = "SOURCE_NOT_FETCHED"

SOURCE_CODES = frozenset({
    SOURCE_TEXT_FROM_OCR, SOURCE_OCR_LOW_CONFIDENCE, SOURCE_TEXT_LAYER_MOJIBAKE,
    SOURCE_TABLE_NOT_RECONSTRUCTED, SOURCE_DOCUMENT_SUPERSEDED,
    SOURCE_VERSION_STATUS_UNKNOWN, SOURCE_STATUS_BASIS_FILENAME,
    SOURCE_CONTENT_DUPLICATED, SOURCE_NO_IMAGE_AVAILABLE, SOURCE_NOT_FETCHED,
})

# `elements.text_source` values that mean a machine read the pixels. `text` is
# the source layer and OCR never writes there (store.py's schema comment), so
# these two values are the whole population -- 25,150 elements, which is
# exactly the registry's count for this code.
_OCR_TEXT_SOURCES = ("ocr", "image_ocr")

# `version_status_basis` that fires SOURCE_STATUS_BASIS_FILENAME. Measured at
# 9 documents on 2026-08-27 -- the corrected count of registry §2.1, not the 6
# that source-refs-design.md published.
_FILENAME_BASIS = "keyword in title/filename"


def source_ref(conn: sqlite3.Connection, ref_id: str, *, dpi: int = 200,
               index=None, tenant: str | None = None) -> dict:
    """The §5.1 shape for one ref. Raises `CropUnavailable` only if unknown.

    `index` is `refs.build_index`'s output; pass it from a batch, because the
    rebuild is ~220 ms and would otherwise be paid once per id.
    """
    idx = refs.build_index(conn) if index is None else index
    locus = refs.resolve(idx, ref_id)
    if locus is None:
        # The one hard failure. `api.py` maps this to 404 `error.unknown_ref`.
        # `refs.resolve`'s docstring: None is never an empty result, because a
        # published value citing an id that resolves to nothing violates
        # obligation 3.
        raise CropUnavailable(
            f"no such ref_id: {ref_id}; nothing in this store produces it")

    filings = _filings(conn, locus.sha256, tenant)
    if not filings:
        # Obligation 7, failing CLOSED. Every filing of these bytes belongs to
        # some other tenant, so this caller may not see the text, the crop, the
        # path or the manufacturer -- and must not learn that the id exists
        # either, which is why this is the same refusal, with the same message,
        # as an id nothing produces. Existence is itself information.
        #
        # This is a placeholder for authorisation, and it is deliberately the
        # strict end of the range: `api.py`'s bearer allowlist authenticates a
        # CALLER and maps to no tenant, so `tenant` is None on every request
        # today and a tenant-owned document is unreachable through the API by
        # anyone, including its owner. That is honest while every document in
        # the corpus is shared (144 of 144) and this branch is unreachable in
        # practice. It stops being adequate the day the first upload lands:
        # obligation 3 then requires the OWNER to resolve their own citation,
        # which needs a token-to-tenant mapping that does not exist. See
        # docs/state-and-gaps.md G48.
        raise CropUnavailable(
            f"no such ref_id: {ref_id}; nothing in this store produces it")
    image, image_problem = _image(conn, ref_id, locus, dpi=dpi, index=idx,
                                  filings=filings)
    return {
        "id": ref_id,
        "belongs_to": locus.sha256,
        "page_no": locus.page_no,
        "text": _text(conn, locus),
        "image": image,
        "warnings": _warnings(conn, locus, filings, image_problem),
    }


def source_refs_batch(conn: sqlite3.Connection, ref_ids: list[str], *,
                      dpi: int = 200, deadline_s: float = 10.0,
                      cap: int = 50, tenant: str | None = None) -> dict:
    """`{"refs": [...], "not_rendered": [...], "deadline_exceeded": bool}`.

    Two refusals, and only one of them is an exception.

    **Over `cap` ids raises `ValueError`** -- `api.py` maps it to 413
    `error.batch_too_large`. The cap is a request-shape error the caller can
    fix by asking for less, so it must be loud and must happen before any work.

    **The deadline never raises.** K3 §1 measures the render distribution as
    bimodal: a batch of 50 is ~1.2 s at the median and ~6.7 s with a single
    p99 element in it, so a screen that happens to include one heavy page must
    still show the other 49. Ids not reached go in `not_rendered` and
    `deadline_exceeded` is true. §7: *a reviewer seeing nothing is the worse
    failure.*

    The deadline bounds this function; it is **not** passed down as a
    subprocess timeout. `render_crop`'s 120 s stays -- K3 §5.3: the failure
    mode of a short timeout is a reviewer seeing nothing, and a render already
    in flight is nearly always cheaper to finish than to repeat.

    An id that resolves to nothing lands in `unknown`, not in `not_rendered`,
    and does not fail the batch: one bad id in a screenful must not cost the
    other 49. The two lists are separated because they ask the caller for
    opposite things -- `not_rendered` is *retry*, `unknown` is *fix the caller*
    -- and a response-level `deadline_exceeded` cannot tell them apart in a
    batch that contains both. Ids are answered in the
    order given and duplicates are not collapsed -- the response lines up with
    the request, and a repeat is a cache hit anyway.
    """
    if len(ref_ids) > cap:
        raise ValueError(
            f"batch of {len(ref_ids)} ids exceeds the cap of {cap}; "
            f"§5.1 fixes it at 50 because a 50-crop batch is already ~6.7 s "
            f"with one p99 render in it")

    # Once per batch, before the clock starts: this is fixed cost, not work
    # the deadline should be spent on.
    index = refs.build_index(conn)

    started = time.monotonic()
    out, not_rendered, unknown, exceeded = [], [], [], False
    for rid in ref_ids:
        if exceeded or (time.monotonic() - started) >= deadline_s:
            exceeded = True
            not_rendered.append(rid)
            continue
        try:
            out.append(source_ref(conn, rid, dpi=dpi, index=index,
                                  tenant=tenant))
        except CropUnavailable:
            # An unresolvable id, or one every filing of which belongs to
            # another tenant -- `source_ref` refuses both identically and on
            # purpose, so a batch cannot be used to probe for the existence of
            # somebody else's ref by watching which list an id lands in. A ref
            # that resolves but cannot be pictured is answered normally with
            # `image: null`.
            unknown.append(rid)
    return {"refs": out, "not_rendered": not_rendered, "unknown": unknown,
            "deadline_exceeded": exceeded}


# --------------------------------------------------------------- assembly

def _filings(conn: sqlite3.Connection, sha256: str,
             tenant: str | None = None) -> list[sqlite3.Row]:
    """Every VISIBLE document record filed against these bytes, in order.

    Usually one. 14 groups here have more, one of them four, and
    `documents.version_status_basis` already differs across one such pair --
    which is why the warnings below union over all of them instead of electing
    a primary.

    Obligation 7. A content hash can be filed under a shared document *and* a
    tenant's upload, so visibility is per filing rather than per hash: the
    bytes stay resolvable through the shared filing, and the upload's
    manufacturer, path and doc_type -- all of which reach the wire through
    `_warnings` and `also_filed_under` -- do not. `tenant=None` is the caller
    with no tenant in hand and sees only SHARED documents, which is the whole
    corpus today; see the note in `source_ref`.
    """
    return conn.execute(
        f"""SELECT d.document_id, d.source_path, d.file_type, d.manufacturer,
                  d.doc_type, d.version_status, d.version_status_basis,
                  d.structural, v.version_id
             FROM document_versions v
             JOIN documents d ON d.document_id = v.document_id
            WHERE v.sha256 = ? AND {visible_sql('d')}
            ORDER BY d.document_id""", (sha256, tenant)).fetchall()


def _text(conn: sqlite3.Connection, locus: refs.Locus) -> str | None:
    """The element's text, or None when the ref does not name exactly one.

    `text or ocr_text` is the package-wide convention (retrieval.py, audit.py):
    the source layer wins and OCR fills in only where there was none, because
    prohibition -- OCR must never overwrite an existing text layer.
    """
    if len(locus.element_ids) != 1:
        return None
    row = conn.execute(
        "SELECT text, ocr_text FROM elements WHERE element_id = ?",
        (locus.element_ids[0],)).fetchone()
    if row is None:
        return None
    return (row["text"] or row["ocr_text"] or "") or None


def _image(conn, ref_id, locus, *, dpi, index, filings):
    """`(image_dict_or_None, problem_or_None)`.

    `problem` is the `SOURCE_*` code and params to publish when there is no
    image, so the caller never has to re-derive *why* from an exception.
    """
    try:
        crop = ensure_crop(conn, ref_id, dpi=dpi, index=index)
    except CropUnavailable as exc:
        return None, _no_image_warning(locus, filings, exc)
    return {"url": relative_url(crop["path"]), "sha256": crop["sha256"],
            "dpi": crop["dpi"]}, None


def _no_image_warning(locus: refs.Locus, filings, exc: CropUnavailable) -> dict:
    """Distinguish "we cannot picture this" from "you have not fetched it".

    A fresh checkout holds every PDF as a ~131-byte LFS pointer, and the
    resulting failure is neither the platform's nor the document's fault -- it
    is one `cli fetch` away. Publishing it as `SOURCE_NO_IMAGE_AVAILABLE`
    would tell a curator the evidence does not exist when it does.

    The test runs the other way round, though: `SOURCE_NOT_FETCHED` may only
    be claimed where fetching would actually help. A page ref has no rectangle
    and a CAD PNG has no poppler renderer, and neither becomes pictureable by
    downloading anything -- so those are settled first, and only a ref that is
    otherwise renderable can be blamed on the corpus being absent.
    """
    pdfs = [r for r in filings if (r["file_type"] or "").lower() == "pdf"]
    if locus.bbox is not None and pdfs and all(
            not (REPO_ROOT / r["source_path"]).is_file()
            or is_lfs_pointer(REPO_ROOT / r["source_path"]) for r in pdfs):
        return {"code": SOURCE_NOT_FETCHED,
                "params": {"subset": _subset_of(pdfs[0])}}
    return {"code": SOURCE_NO_IMAGE_AVAILABLE, "params": {"reason": str(exc)}}


def _subset_of(row) -> str:
    """The narrowest `cli fetch --subset` that would bring this file down.

    The predicates come from `distribution.SUBSETS` rather than being spelled
    out again here: two definitions of "which subset is this file in" would
    drift, and the operator acts on this string.
    """
    from .distribution import SUBSETS
    synthetic = {"source_path": row["source_path"],
                 "structural_subdir": bool(row["structural"])}
    named = [name for name, pred in SUBSETS.items()
             if name != "all" and pred(synthetic)]
    return sorted(named)[0] if named else "all"


def _warnings(conn: sqlite3.Connection, locus: refs.Locus,
              filings: list[sqlite3.Row], image_problem: dict | None) -> list[dict]:
    """Every `SOURCE_*` code that applies to this ref, sorted by code.

    Sorted because this is published into an immutable snapshot: two builds
    over identical knowledge must produce identical bytes, and SQLite's row
    order is not a promise.
    """
    found: list[dict] = []

    # --- element level: did a machine read these pixels? -------------------
    if locus.element_ids:
        marks = "?" * len(locus.element_ids)
        rows = conn.execute(
            f"""SELECT text_source, ocr_confidence FROM elements
                 WHERE element_id IN ({','.join(marks)})""",
            locus.element_ids).fetchall()
        ocr = [r for r in rows if (r["text_source"] or "") in _OCR_TEXT_SOURCES]
        if ocr:
            # The lowest confidence among the elements this id covers. A ref
            # that is not injective (9,929 are not) publishes the weakest
            # reading it might be showing, never the flattering one.
            scores = [r["ocr_confidence"] for r in ocr
                      if r["ocr_confidence"] is not None]
            found.append({"code": SOURCE_TEXT_FROM_OCR,
                          "params": {"confidence": _round(min(scores))
                                     if scores else None}})

    # --- page and document level, unioned over every filing ----------------
    superseded_by: set[str] = set()
    is_superseded = status_unknown = basis_is_filename = False
    mojibake_pages = 0
    low_conf_fired = False
    low_conf: float | None = None
    table_not_reconstructed = False

    for row in filings:
        doc_id = row["document_id"]
        status = (row["version_status"] or "").lower()
        if status == "superseded":
            is_superseded = True
            superseded_by |= _successors(conn, doc_id)
        elif status == "unknown":
            status_unknown = True
        if (row["version_status_basis"] or "") == _FILENAME_BASIS:
            basis_is_filename = True

        mojibake_pages = max(mojibake_pages,
                             _issue_count(conn, doc_id, "mojibake_text_layer"))
        page_kinds = {r["kind"] for r in conn.execute(
            """SELECT DISTINCT kind FROM quality_issues
                WHERE document_id = ? AND page_no = ?""",
            (doc_id, locus.page_no))}
        if "table_not_reconstructed" in page_kinds:
            table_not_reconstructed = True
        if "low_ocr_confidence" in page_kinds:
            # Take the threshold from the issue the extractor already
            # recorded, never by re-applying a literal here: a second copy of
            # `< 70` would be a second definition of "low", free to drift from
            # extract.py's. The issue firing is the warning; the number is a
            # detail that may be missing, and a missing number must not
            # silently suppress a warning the extractor did raise.
            low_conf_fired = True
            conf = conn.execute(
                """SELECT p.ocr_mean_confidence FROM pages p
                    WHERE p.version_id = ? AND p.page_no = ?""",
                (row["version_id"], locus.page_no)).fetchone()
            if conf is not None and conf["ocr_mean_confidence"] is not None:
                value = conf["ocr_mean_confidence"]
                low_conf = value if low_conf is None else min(low_conf, value)

    if is_superseded:
        # registry §2.1: fire on the *status*, not on the edge. Three of the
        # nine superseded documents have no successor recorded anywhere, and
        # suppressing the warning because the param is empty would hide
        # exactly the weakest three. The param is a list because
        # doc-8727ba0fd4d4 fans out to seven.
        found.append({"code": SOURCE_DOCUMENT_SUPERSEDED,
                      "params": {"superseded_by": sorted(superseded_by)}})
    if status_unknown:
        found.append({"code": SOURCE_VERSION_STATUS_UNKNOWN, "params": {}})
    if basis_is_filename:
        found.append({"code": SOURCE_STATUS_BASIS_FILENAME, "params": {}})
    if mojibake_pages:
        found.append({"code": SOURCE_TEXT_LAYER_MOJIBAKE,
                      "params": {"pages_affected": mojibake_pages}})
    if table_not_reconstructed:
        found.append({"code": SOURCE_TABLE_NOT_RECONSTRUCTED, "params": {}})
    if low_conf_fired:
        found.append({"code": SOURCE_OCR_LOW_CONFIDENCE,
                      "params": {"confidence": _round(low_conf)
                                 if low_conf is not None else None}})

    also = _also_filed_under(conn, filings)
    if also:
        found.append({"code": SOURCE_CONTENT_DUPLICATED,
                      "params": {"also_filed_under": also}})

    if image_problem is not None:
        found.append(image_problem)

    return sorted(found, key=lambda w: w["code"])


def _successors(conn: sqlite3.Connection, document_id: str) -> set[str]:
    """Content hashes of the documents that supersede this one.

    A `superseded_by` edge reads subject -> object: the *from* side is the
    superseded document. Marking the wrong side once labelled every current
    NOA superseded; `tests/test_versions.py` guards the ingest side and this
    query must agree with it.

    Content hashes, not document ids: `belongs_to` is a content hash
    everywhere else on this wire, and a document id is an internal handle
    Planning cannot resolve to anything.
    """
    return {r["sha256"] for r in conn.execute(
        """SELECT DISTINCT v.sha256
             FROM relations r
             JOIN document_versions v ON v.document_id = r.to_document_id
            WHERE r.from_document_id = ? AND r.relation_type = 'superseded_by'""",
        (document_id,))}


def _also_filed_under(conn: sqlite3.Connection,
                      filings: list[sqlite3.Row]) -> list[dict]:
    """`{manufacturer, doc_type}` for every other filing of these bytes.

    registry §5: the class is a property of the bytes, the filing is a
    property of the catalogue. The group is the union of two things that
    coincide today and need not: the document rows sharing this content hash,
    and their `same_content_as` peers. Taking only the edges would report
    nothing when both filings point at each other and neither is "other"; the
    first filing is dropped because it is the one the ref is already about.
    """
    own = [r["document_id"] for r in filings]
    group: dict[str, tuple] = {}
    for row in filings:
        for peer in conn.execute(
                """SELECT d.document_id, d.manufacturer, d.doc_type
                     FROM relations r
                     JOIN documents d ON d.document_id = r.to_document_id
                    WHERE r.from_document_id = ?
                      AND r.relation_type = 'same_content_as'""",
                (row["document_id"],)):
            group[peer["document_id"]] = (peer["manufacturer"], peer["doc_type"])
    for row in filings:
        group.setdefault(row["document_id"],
                         (row["manufacturer"], row["doc_type"]))
    group.pop(own[0], None)
    return [{"manufacturer": group[k][0], "doc_type": group[k][1]}
            for k in sorted(group)]


def _issue_count(conn: sqlite3.Connection, document_id: str, kind: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM quality_issues WHERE document_id = ? AND kind = ?",
        (document_id, kind)).fetchone()[0]


def _round(value: float) -> float:
    """One decimal, matching the §5.1 exemplar's `95.6`.

    A confidence is a measurement to about a percent; publishing
    `95.60000000000001` into an immutable snapshot would be noise that no two
    float implementations need agree on.
    """
    return round(float(value), 1)
