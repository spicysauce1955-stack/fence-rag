"""Obligation 7 — tenant isolation enforced in code, not by convention.

    > 7. **Tenant isolation is enforced in code**, not by convention. A snapshot
    >    for one tenant contains nothing belonging to another.

At ratification this platform declared the obligation *unbuilt*, in the bluntest
terms `10-ratification-v1.0.md` §3.2 uses about anything:

    > There is no tenant concept anywhere in this store — one corpus, no boundary
    > to enforce in code. *Enforced by convention* would be a generous
    > description of something that does not exist at all.

`build_snapshot(tenant=...)` took a tenant and stamped it on the object. Nothing
read it. A tenant was a label, and a label is exactly what obligation 7 says a
boundary must not be.

The shape of the fix follows the closure rule's, deliberately. Closure is not
validated after the fact — minting a `SourceRef` registers its `SourceDoc`, so a
snapshot citing a document it does not carry *cannot be built*. Tenancy uses the
same choke point: every published value's provenance goes through
`SnapshotBuilder.source_ref`, so a check there makes a cross-tenant value
unpublishable rather than filtered.

The three leak paths are tested separately because two of them do not go through
a `SourceRef` at all. `also_filed_as` and `superseded_by` publish facts about
*other* documents that happen to share bytes or an edge with a cited one, and
neither is minted. A gate that only guarded `source_ref` would publish tenant
B's manufacturer to tenant A and raise nothing.
"""
import json
import sqlite3
import unittest

import context  # noqa: F401  -- puts the repo root on sys.path
from fence_evidence import store
from fence_evidence.model import Element, ExtractedDocument, Page
from fence_evidence.snapshot import SnapshotBuilder, TenantLeak, build_snapshot

TOOLS = {"pdftotext": "24.02.0", "tesseract": "5.3.4"}


def manifest_row(path: str, *, manufacturer: str, doc_type: str = "spec_sheet",
                 owner_tenant: str | None = None) -> dict:
    from fence_evidence.ids import doc_id_for
    row = {"doc_id": doc_id_for(path), "source_path": path, "file_type": "pdf",
           "corpus_track": "us", "manufacturer": manufacturer,
           "title": path.rsplit("/", 1)[-1], "doc_type": doc_type,
           "file_size_bytes": 1234}
    if owner_tenant is not None:
        row["owner_tenant"] = owner_tenant
    return row


# A lexeme-led warning, so `warnings()` publishes something and therefore mints
# a ref: a fixture whose pages cite nothing produces an empty snapshot, and an
# empty snapshot passes every isolation assertion vacuously.
WARNING_TEXT = ("WARNING: Failure to comply with these instructions may result "
                "in personal injury.")


def extracted(sha: str, path: str) -> ExtractedDocument:
    els = [
        Element(element_type="paragraph", text=WARNING_TEXT,
                bbox=(72.0, 100.0, 540.0, 120.0), ordinal=0),
        Element(element_type="paragraph",
                text="Set posts in a footing 36 in. deep at Exposure C.",
                bbox=(72.0, 130.0, 540.0, 150.0), ordinal=1),
    ]
    page = Page(page_no=1, width=612.0, height=792.0,
                extraction_method="pdf_text_layer", elements=els,
                has_text_layer=True, text_char_count=len(WARNING_TEXT) + 48)
    return ExtractedDocument(source_path=path, sha256=sha, file_type="pdf",
                             pages=[page])


def fresh_store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    store.migrate(conn)
    return conn


def start_run(conn: sqlite3.Connection) -> str:
    fp = store.tool_fingerprint(TOOLS)
    seq = conn.execute("SELECT COUNT(*) FROM extraction_runs").fetchone()[0]
    run_id = f"run-test-{fp}-{seq}"
    conn.execute(
        "INSERT INTO extraction_runs(run_id, started_at, tool_versions, "
        "tool_fingerprint, pipeline_version, notes) VALUES (?,?,?,?,?,?)",
        (run_id, store.now(), json.dumps(TOOLS, sort_keys=True), fp, "1.0", ""))
    conn.commit()
    return run_id


def add_doc(conn, run_id, *, path, sha, manufacturer, owner_tenant=None,
            doc_type="spec_sheet") -> str:
    row = manifest_row(path, manufacturer=manufacturer, doc_type=doc_type,
                       owner_tenant=owner_tenant)
    store.write_extracted(conn, extracted(sha, path), row, run_id)
    return row["doc_id"]


def only_element(conn, document_id: str) -> str:
    return conn.execute("SELECT element_id FROM elements WHERE document_id=? "
                        "ORDER BY ordinal LIMIT 1",
                        (document_id,)).fetchone()["element_id"]


SHARED_SHA = "a" * 64
ACME_SHA = "b" * 64
GLOBEX_SHA = "c" * 64


class TestTheColumnExistsAndMeansNothingByDefault(unittest.TestCase):
    """A column whose migration invents ownership is worse than no column."""

    def test_a_fresh_store_has_owner_tenant(self):
        conn = fresh_store()
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
            self.assertIn("owner_tenant", cols)
        finally:
            conn.close()

    def test_a_corpus_document_is_owned_by_nobody(self):
        """NULL is shared knowledge. Everything in this corpus is shared."""
        conn = fresh_store()
        try:
            run = start_run(conn)
            doc = add_doc(conn, run, path="manuals/acme/g.pdf", sha=SHARED_SHA,
                          manufacturer="acme")
            owner = conn.execute("SELECT owner_tenant FROM documents WHERE "
                                 "document_id=?", (doc,)).fetchone()[0]
            self.assertIsNone(owner)
        finally:
            conn.close()

    def test_migrating_an_older_store_leaves_every_row_shared(self):
        """The column arrives on 144 existing rows. It must arrive empty.

        Defaulting them to the operator's tenant would silently make the whole
        corpus one tenant's private property — the exact inversion of obligation
        7, arriving through the migration rather than through a leak.
        """
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            store.migrate(conn)
            run = start_run(conn)
            add_doc(conn, run, path="manuals/acme/g.pdf", sha=SHARED_SHA,
                    manufacturer="acme")
            conn.execute("ALTER TABLE documents DROP COLUMN owner_tenant")
            conn.commit()
            added = store.ensure_columns(conn)
            self.assertIn("documents.owner_tenant", added)
            owners = [r[0] for r in conn.execute(
                "SELECT owner_tenant FROM documents")]
            self.assertEqual(owners, [None])
        finally:
            conn.close()


class TestOwnershipIsNotSilentlyReassigned(unittest.TestCase):
    def setUp(self):
        self.conn = fresh_store()
        self.run = start_run(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_an_upload_records_its_owner(self):
        doc = add_doc(self.conn, self.run, path="uploads/acme/site.pdf",
                      sha=ACME_SHA, manufacturer="acme", owner_tenant="acme")
        owner = self.conn.execute("SELECT owner_tenant FROM documents WHERE "
                                  "document_id=?", (doc,)).fetchone()[0]
        self.assertEqual(owner, "acme")

    def test_re_ingesting_the_same_owner_is_fine(self):
        add_doc(self.conn, self.run, path="uploads/acme/site.pdf", sha=ACME_SHA,
                manufacturer="acme", owner_tenant="acme")
        add_doc(self.conn, self.run, path="uploads/acme/site.pdf", sha=ACME_SHA,
                manufacturer="acme", owner_tenant="acme")

    def test_re_parenting_a_document_raises(self):
        """A manifest that moves a document between tenants is a leak, not an
        update. `upsert_document` updates nine fields on conflict; if ownership
        joined them, a re-ingest would hand one tenant's document to another and
        the ON CONFLICT clause would be the only record of it."""
        add_doc(self.conn, self.run, path="uploads/acme/site.pdf", sha=ACME_SHA,
                manufacturer="acme", owner_tenant="acme")
        with self.assertRaises(TenantLeak):
            add_doc(self.conn, self.run, path="uploads/acme/site.pdf",
                    sha=ACME_SHA, manufacturer="acme", owner_tenant="globex")

    def test_an_omitted_owner_does_not_release_a_document(self):
        """The corpus manifest carries no `owner_tenant`. Re-running `ingest`
        over a store holding tenant uploads must not quietly free them."""
        doc = add_doc(self.conn, self.run, path="uploads/acme/site.pdf",
                      sha=ACME_SHA, manufacturer="acme", owner_tenant="acme")
        add_doc(self.conn, self.run, path="uploads/acme/site.pdf", sha=ACME_SHA,
                manufacturer="acme")
        owner = self.conn.execute("SELECT owner_tenant FROM documents WHERE "
                                  "document_id=?", (doc,)).fetchone()[0]
        self.assertEqual(owner, "acme")

    def test_claiming_a_shared_document_raises(self):
        """Shared knowledge is not claimable. The corpus belongs to everyone."""
        add_doc(self.conn, self.run, path="manuals/acme/g.pdf", sha=SHARED_SHA,
                manufacturer="acme")
        with self.assertRaises(TenantLeak):
            add_doc(self.conn, self.run, path="manuals/acme/g.pdf",
                    sha=SHARED_SHA, manufacturer="acme", owner_tenant="acme")


class _TwoTenants(unittest.TestCase):
    """One shared document, one owned by `acme`, one owned by `globex`."""

    def setUp(self):
        self.conn = fresh_store()
        run = start_run(self.conn)
        self.shared = add_doc(self.conn, run, path="manuals/acme/g.pdf",
                              sha=SHARED_SHA, manufacturer="acme")
        self.acme = add_doc(self.conn, run, path="uploads/acme/site.pdf",
                            sha=ACME_SHA, manufacturer="acme",
                            owner_tenant="acme")
        self.globex = add_doc(self.conn, run, path="uploads/globex/site.pdf",
                              sha=GLOBEX_SHA, manufacturer="globex",
                              owner_tenant="globex")

    def tearDown(self):
        self.conn.close()


class TestMintingIsTheBoundary(_TwoTenants):
    def test_shared_knowledge_is_visible_to_every_tenant(self):
        for tenant in ("acme", "globex"):
            b = SnapshotBuilder(self.conn, tenant=tenant, regime="us_astm")
            ref = b.source_ref(only_element(self.conn, self.shared))
            self.assertEqual(ref.belongs_to, SHARED_SHA)

    def test_a_tenant_reaches_its_own_upload(self):
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        self.assertEqual(b.source_ref(only_element(self.conn, self.acme))
                         .belongs_to, ACME_SHA)

    def test_a_tenant_cannot_mint_a_ref_into_another_tenants_document(self):
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        with self.assertRaises(TenantLeak):
            b.source_ref(only_element(self.conn, self.globex))

    def test_a_refused_mint_registers_nothing(self):
        """A gate that raises after registering the document has already leaked
        it: `source_docs()` is read at the end of the build, not at the raise."""
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        with self.assertRaises(TenantLeak):
            b.source_ref(only_element(self.conn, self.globex))
        self.assertEqual([d.content_hash for d in b.source_docs()], [])

    def test_the_message_names_both_tenants(self):
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        with self.assertRaises(TenantLeak) as caught:
            b.source_ref(only_element(self.conn, self.globex))
        self.assertIn("acme", str(caught.exception))
        self.assertIn("globex", str(caught.exception))


class TestTheSideChannels(_TwoTenants):
    """Two published fields name documents that were never minted."""

    def test_also_filed_as_does_not_publish_another_tenants_filing(self):
        """14 groups of byte-identical files are filed under different
        manufacturers here, and `also_filed_as` exists to make that visible. The
        same mechanism, pointed at an upload, publishes tenant B's manufacturer
        and doc_type inside tenant A's snapshot."""
        run = start_run(self.conn)
        add_doc(self.conn, run, path="uploads/globex/copy.pdf", sha=SHARED_SHA,
                manufacturer="globex", doc_type="warranty",
                owner_tenant="globex")
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        b.source_ref(only_element(self.conn, self.shared))
        doc, = [d for d in b.source_docs() if d.content_hash == SHARED_SHA]
        self.assertEqual(doc.also_filed_as, (),
                         "another tenant's filing was published")

    def test_also_filed_as_still_publishes_a_shared_filing(self):
        """The guard must not be a blanket suppression: a second SHARED filing
        of the same bytes is exactly what the field is for."""
        run = start_run(self.conn)
        add_doc(self.conn, run, path="manuals/other/copy.pdf", sha=SHARED_SHA,
                manufacturer="other", doc_type="warranty")
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        b.source_ref(only_element(self.conn, self.shared))
        doc, = [d for d in b.source_docs() if d.content_hash == SHARED_SHA]
        self.assertEqual(doc.also_filed_as,
                         ({"manufacturer": "other", "doc_type": "warranty"},))

    def test_superseded_by_does_not_publish_another_tenants_hash(self):
        """A `superseded_by` edge publishes the successor's content hash. If the
        successor is another tenant's upload, that hash is theirs."""
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, self.globex, "superseded_by", "fixture", 1.0))
        self.conn.commit()
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        b.source_ref(only_element(self.conn, self.shared))
        doc, = [d for d in b.source_docs() if d.content_hash == SHARED_SHA]
        self.assertEqual(doc.superseded_by, ())

    def test_superseded_by_still_publishes_a_shared_successor(self):
        run = start_run(self.conn)
        successor = add_doc(self.conn, run, path="manuals/acme/g2.pdf",
                            sha="d" * 64, manufacturer="acme")
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, successor, "superseded_by", "fixture", 1.0))
        self.conn.commit()
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        b.source_ref(only_element(self.conn, self.shared))
        doc, = [d for d in b.source_docs() if d.content_hash == SHARED_SHA]
        self.assertEqual(doc.superseded_by, ("d" * 64,))

    def test_a_tenant_sees_the_successor_it_owns(self):
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, self.acme, "superseded_by", "fixture", 1.0))
        self.conn.commit()
        b = SnapshotBuilder(self.conn, tenant="acme", regime="us_astm")
        b.source_ref(only_element(self.conn, self.shared))
        doc, = [d for d in b.source_docs() if d.content_hash == SHARED_SHA]
        self.assertEqual(doc.superseded_by, (ACME_SHA,))


class TestPublishedValuesAreScopedToo(_TwoTenants):
    """`parameters` is the only snapshot section that carries published VALUES.

    `warnings` and `gaps` carry text and work items; a `ParameterTable` row is a
    number a planner builds to. It is empty today only because A1 un-promoted
    everything, so `facts WHERE from_candidate_id IS NOT NULL` matches nothing —
    which meant an adversarial mutation could delete the tenant scoping from
    `build_parameter_tables`, or drop `tenant=` at the call site in
    `build_snapshot`, and the entire suite still passed. The first fact a
    reviewer promotes is the moment that becomes load-bearing.
    """

    def _promote(self, document_id, *, value="24", tenant_owned):
        """One promoted fact, the shape `build_parameter_tables` selects."""
        el = only_element(self.conn, document_id)
        row = self.conn.execute(
            "SELECT version_id, page_no FROM elements WHERE element_id=?",
            (el,)).fetchone()
        self.conn.execute(
            """INSERT INTO table_read_candidates(document_id, version_id, page_no,
                   crop_path, reader, reader_kind, row_index, col_index, value,
                   review_status, reviewer, reviewed_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, row["version_id"], row["page_no"], "crop.png",
             "fixture-reader", "human", 0, 0, value, "accepted", "fixture",
             store.now(), store.now()))
        candidate_id = self.conn.execute(
            "SELECT last_insert_rowid()").fetchone()[0]
        self.conn.execute(
            """INSERT INTO facts(document_id, version_id, page_no, element_id,
                   fact_type, subject, value_original, value_normalized,
                   unit_original, unit_normalized, conditions, evidence_text,
                   extractor, review_status, condition_basis, from_candidate_id,
                   created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, row["version_id"], row["page_no"], el,
             "footing_depth_in", "post", f'{value}"', float(value), "in", "in",
             "{}", "fixture", "table-read:fixture", "reviewed", "stated",
             candidate_id, store.now()))
        self.conn.commit()

    def test_a_promoted_fact_on_an_upload_is_not_in_another_tenants_tables(self):
        from fence_evidence.parameters import build_parameter_tables
        self._promote(self.globex, value="24", tenant_owned=True)
        tables, _gaps = build_parameter_tables(self.conn, tenant="acme")
        blob = json.dumps(tables, sort_keys=True, default=str)
        self.assertNotIn("globex", blob)
        self.assertNotIn("609600", blob, "the other tenant's value was published")

    def test_the_owner_does_get_its_own_promoted_fact(self):
        """Scoping must not be a blanket refusal, or the feature is useless."""
        from fence_evidence.parameters import build_parameter_tables
        self._promote(self.acme, value="24", tenant_owned=True)
        tables, _gaps = build_parameter_tables(self.conn, tenant="acme")
        self.assertTrue(tables, "the owner's own promoted fact did not publish")

    def test_a_whole_snapshot_carries_no_foreign_parameter_row(self):
        """The call site, not just the function: `build_snapshot` has to pass
        the tenant down, and dropping that argument was the other mutation that
        survived the suite."""
        self._promote(self.globex, value="24", tenant_owned=True)
        self._promote(self.shared, value="30", tenant_owned=False)
        snap = build_snapshot(tenant="acme", conn=self.conn)
        blob = json.dumps(snap, sort_keys=True, default=str)
        self.assertNotIn(GLOBEX_SHA, blob)
        self.assertNotIn("globex", blob)
        self.assertTrue(snap["parameters"], "the shared fact should still publish")


class TestAWholeSnapshotCarriesNothingForeign(_TwoTenants):
    def test_the_other_tenants_bytes_appear_nowhere_in_the_object(self):
        """The obligation, checked the blunt way: serialise the whole snapshot
        and look for the other tenant's content hash anywhere in it — inside a
        ref id's `belongs_to`, a gap's `cites`, a warning's `attaches_to`, or a
        field nobody has thought of yet."""
        snap = build_snapshot(tenant="acme", conn=self.conn)
        blob = json.dumps(snap, sort_keys=True, default=str)
        self.assertNotIn(GLOBEX_SHA, blob)
        self.assertNotIn("globex", blob)

    def test_a_snapshot_still_carries_shared_and_own_content(self):
        snap = build_snapshot(tenant="acme", conn=self.conn)
        blob = json.dumps(snap, sort_keys=True, default=str)
        self.assertIn(SHARED_SHA, blob)

    def test_two_tenants_over_the_same_shared_corpus_agree(self):
        """Nothing here is tenant-specific yet, so the only difference between
        the two objects should be the tenant field itself. If the ids differ for
        any other reason the isolation gate is filtering shared knowledge."""
        conn = fresh_store()
        try:
            run = start_run(conn)
            add_doc(conn, run, path="manuals/acme/g.pdf", sha=SHARED_SHA,
                    manufacturer="acme")
            a = build_snapshot(tenant="acme", conn=conn)
            b = build_snapshot(tenant="globex", conn=conn)
            self.assertEqual(a["source_docs"], b["source_docs"])
            self.assertNotEqual(a["snapshot_id"], b["snapshot_id"],
                                "the tenant is a hashed member; two tenants "
                                "must not share a snapshot id")
        finally:
            conn.close()


class TestTheDiscoveryApiFailsClosed(_TwoTenants):
    """`GET /source-refs/{id}` resolves a `ref_id` with NO tenant in scope.

    `api.py`'s bearer allowlist authenticates a caller and maps to no tenant, so
    the resolver is called with `tenant=None`. That is a real hole the moment a
    tenant uploads a document: the snapshot builder would refuse to publish a
    citation into it, but the Discovery endpoint would happily render the crop
    to anyone holding any allowlisted token.

    So it fails CLOSED — with `tenant=None` only shared documents resolve — and
    the refusal is byte-identical to "no such ref_id", because telling a caller
    that an id exists but is not theirs is itself the leak in miniature.
    """

    def _ref(self, document_id):
        from fence_evidence import refs
        row = self.conn.execute(
            """SELECT v.sha256, e.page_no, e.bbox FROM elements e
                 JOIN document_versions v ON v.version_id = e.version_id
                WHERE e.document_id = ? AND e.bbox IS NOT NULL
                ORDER BY e.ordinal LIMIT 1""", (document_id,)).fetchone()
        return refs.ref_id(row["sha256"], row["page_no"], row["bbox"])

    def test_a_shared_ref_resolves_with_no_tenant(self):
        from fence_evidence import sourcerefs
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        self.assertEqual(got["belongs_to"], SHARED_SHA)

    def test_an_owned_ref_does_not_resolve_for_a_caller_with_no_tenant(self):
        from fence_evidence import sourcerefs
        from fence_evidence.cropcache import CropUnavailable
        with self.assertRaises(CropUnavailable):
            sourcerefs.source_ref(self.conn, self._ref(self.acme))

    def test_the_refusal_is_indistinguishable_from_an_unknown_id(self):
        """Existence is information. Two refusals that differ let a caller
        enumerate another tenant's refs by watching the error text."""
        from fence_evidence import sourcerefs
        from fence_evidence.cropcache import CropUnavailable
        real = self._ref(self.globex)
        fake = "0" * 16
        messages = []
        for rid in (real, fake):
            with self.assertRaises(CropUnavailable) as caught:
                sourcerefs.source_ref(self.conn, rid)
            messages.append(str(caught.exception).replace(rid, "<id>"))
        self.assertEqual(messages[0], messages[1])

    def test_an_owned_ref_resolves_for_its_owner(self):
        """The gate is about visibility, not a blanket refusal -- so that when a
        token-to-tenant mapping does arrive, the resolver already works."""
        from fence_evidence import sourcerefs
        got = sourcerefs.source_ref(self.conn, self._ref(self.acme),
                                    tenant="acme")
        self.assertEqual(got["belongs_to"], ACME_SHA)

    def test_a_batch_puts_a_foreign_ref_in_unknown_not_not_rendered(self):
        """`unknown` means 'fix the caller' and `not_rendered` means 'retry'.
        A foreign ref must land in the same list an unknown id does, or the two
        lists become an existence oracle."""
        from fence_evidence import sourcerefs
        foreign = self._ref(self.globex)
        out = sourcerefs.source_refs_batch(
            self.conn, [self._ref(self.shared), foreign, "0" * 16])
        self.assertEqual(sorted(out["unknown"]), sorted([foreign, "0" * 16]))
        self.assertEqual(out["not_rendered"], [])
        self.assertEqual([r["belongs_to"] for r in out["refs"]], [SHARED_SHA])

    def test_a_same_content_as_edge_does_not_carry_a_filing_across(self):
        """`_also_filed_under` is a UNION of two halves and only one was scoped.

        `filings` arrives scoped by content hash, but the other half walks a
        `same_content_as` edge into `documents` and takes the peer's
        manufacturer and doc_type -- the exact pair the snapshot side refuses to
        publish across a tenant boundary. The earlier test missed it because a
        fixture that merely shares a sha256 has no edge between the two rows;
        `relations.py` writes those, and this one writes it by hand.
        """
        from fence_evidence import sourcerefs
        run = start_run(self.conn)
        peer = add_doc(self.conn, run, path="uploads/globex/copy.pdf",
                       sha="e" * 64, manufacturer="globex",
                       doc_type="warranty", owner_tenant="globex")
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, peer, "same_content_as", "fixture", 1.0))
        self.conn.commit()
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        blob = json.dumps(got, sort_keys=True, default=str)
        self.assertNotIn("globex", blob)

    def test_a_same_content_as_edge_to_a_shared_peer_still_carries(self):
        from fence_evidence import sourcerefs
        run = start_run(self.conn)
        peer = add_doc(self.conn, run, path="manuals/other/copy.pdf",
                       sha="f" * 64, manufacturer="other", doc_type="warranty")
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, peer, "same_content_as", "fixture", 1.0))
        self.conn.commit()
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        blob = json.dumps(got, sort_keys=True, default=str)
        self.assertIn("other", blob)

    def test_a_superseding_upload_does_not_reach_the_discovery_warning(self):
        """`SOURCE_DOCUMENT_SUPERSEDED` publishes the successor's content hash.
        Same hole as the snapshot side's `_successors`, on the Discovery side,
        missed because the boundary was built one file over."""
        from fence_evidence import sourcerefs
        self.conn.execute("UPDATE documents SET version_status='superseded' "
                          "WHERE document_id=?", (self.shared,))
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, self.globex, "superseded_by", "fixture", 1.0))
        self.conn.commit()
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        blob = json.dumps(got, sort_keys=True, default=str)
        self.assertNotIn(GLOBEX_SHA, blob)

    def test_a_superseding_shared_document_still_reaches_it(self):
        from fence_evidence import sourcerefs
        run = start_run(self.conn)
        successor = add_doc(self.conn, run, path="manuals/acme/g2.pdf",
                            sha="d" * 64, manufacturer="acme")
        self.conn.execute("UPDATE documents SET version_status='superseded' "
                          "WHERE document_id=?", (self.shared,))
        self.conn.execute(
            "INSERT INTO relations(from_document_id, to_document_id, "
            "relation_type, basis, confidence) VALUES (?,?,?,?,?)",
            (self.shared, successor, "superseded_by", "fixture", 1.0))
        self.conn.commit()
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        blob = json.dumps(got, sort_keys=True, default=str)
        self.assertIn("d" * 64, blob)

    def test_shared_bytes_stay_reachable_when_a_tenant_also_files_them(self):
        """A content hash filed under BOTH a shared document and an upload is
        shared content. Visibility is per filing, not per hash -- refusing the
        hash would make the tenant's copy censor everyone else's evidence."""
        from fence_evidence import sourcerefs
        run = start_run(self.conn)
        add_doc(self.conn, run, path="uploads/globex/copy.pdf", sha=SHARED_SHA,
                manufacturer="globex", doc_type="warranty",
                owner_tenant="globex")
        got = sourcerefs.source_ref(self.conn, self._ref(self.shared))
        self.assertEqual(got["belongs_to"], SHARED_SHA)
        blob = json.dumps(got, sort_keys=True, default=str)
        self.assertNotIn("globex", blob,
                         "the other tenant's filing reached the wire through "
                         "a SOURCE_CONTENT_DUPLICATED warning")


class TestTheTenantIdentifierItself(unittest.TestCase):
    """`contract.md` §2.1 reserves two namespaces: `shared` and `mfr/<x>`.

    A tenant called `shared` would make its private uploads indistinguishable
    from global knowledge in every id that namespaces on it.
    """

    def setUp(self):
        self.conn = fresh_store()
        run = start_run(self.conn)
        add_doc(self.conn, run, path="manuals/acme/g.pdf", sha=SHARED_SHA,
                manufacturer="acme")

    def tearDown(self):
        self.conn.close()

    def test_shared_is_reserved(self):
        with self.assertRaises(ValueError):
            build_snapshot(tenant="shared", conn=self.conn)

    def test_the_manufacturer_namespace_is_reserved(self):
        with self.assertRaises(ValueError):
            build_snapshot(tenant="mfr/certainteed", conn=self.conn)

    def test_an_empty_tenant_is_refused(self):
        with self.assertRaises(ValueError):
            build_snapshot(tenant="", conn=self.conn)

    def test_default_may_build_but_may_not_own(self):
        """The asymmetry is deliberate and both halves matter.

        `cli.py` builds the operator's global snapshot as `--tenant default`,
        and the published snapshot 83a227d4 carries that string inside its
        hashed members — renaming it would change the id and break obligation
        1's continuity for a tidy-up. But a real tenant owning documents under
        that name would see its private uploads appear in the build everybody
        reads as shared, which is exactly the collision `shared` is reserved to
        prevent. So: legal to build as, refused as an owner.
        """
        from fence_evidence.tenancy import validate_owner, validate_tenant
        self.assertEqual(validate_tenant("default"), "default")
        with self.assertRaises(ValueError):
            validate_owner("default")
        with self.assertRaises(ValueError):
            validate_owner("shared")
        self.assertEqual(validate_owner("acme"), "acme")

    def test_the_published_snapshot_id_did_not_move(self):
        """The reason `default` stays buildable, asserted rather than asserted
        about. If this ever fails, a naming change has silently re-cut a
        published object."""
        snap = build_snapshot(tenant="default", conn=self.conn)
        self.assertEqual(snap["tenant"], "default")

    def test_a_document_cannot_be_owned_by_the_global_build(self):
        conn = fresh_store()
        try:
            run = start_run(conn)
            with self.assertRaises(ValueError):
                add_doc(conn, run, path="uploads/x/site.pdf", sha=ACME_SHA,
                        manufacturer="x", owner_tenant="default")
        finally:
            conn.close()

    def test_an_ordinary_tenant_is_accepted(self):
        snap = build_snapshot(tenant="acme", conn=self.conn)
        self.assertEqual(snap["tenant"], "acme")


if __name__ == "__main__":
    unittest.main()
