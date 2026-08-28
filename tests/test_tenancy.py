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

    def test_an_ordinary_tenant_is_accepted(self):
        snap = build_snapshot(tenant="acme", conn=self.conn)
        self.assertEqual(snap["tenant"], "acme")


if __name__ == "__main__":
    unittest.main()
