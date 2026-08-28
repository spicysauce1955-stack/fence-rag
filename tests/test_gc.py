"""G11: garbage-collecting orphaned derived images.

`workspace/derived/` is a cache of page images, region crops, NOA table-candidate
crops and the review-crop cache. Nothing has ever removed a file from it, so a
re-extraction that moves a bbox (or a document that leaves the corpus) leaves
its images behind forever. These tests pin the two properties that make a
collector safe to run at all:

1. it is a dry run unless `--apply` is passed, and
2. nothing reachable is ever collected -- where "reachable" includes a crop
   whose only claimant is an *immutable published snapshot*, because a
   published citation that stops resolving is an obligation-3 violation that
   can never be repaired.

Every fixture lives under `workspace/tests/`, not `/tmp`: `paths.ensure_writable`
refuses anything outside the workspace and the collector goes through it.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from context import ROOT  # noqa: F401  (puts the repo root on sys.path)

from fence_evidence import gc as gcmod
from fence_evidence.paths import TESTS_DIR, CorpusWriteError

REF_A = "0d9a86f63cc477e7"
REF_B = "1234567890abcdef"
FP = "64e1ee02ac41867f"


def _write(path: Path, data: bytes = b"png-bytes") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _schema(conn: sqlite3.Connection) -> None:
    """The columns the collector reads, and nothing else.

    Deliberately not `store.SCHEMA`: this test is about reachability, and
    building the real 18-table store would make it a store test that happens
    to exercise gc.
    """
    conn.executescript("""
        CREATE TABLE pages (page_id TEXT PRIMARY KEY, page_image_path TEXT);
        CREATE TABLE elements (element_id TEXT PRIMARY KEY, region_image_path TEXT);
        CREATE TABLE assets (asset_id TEXT PRIMARY KEY, path TEXT);
        CREATE TABLE table_read_candidates (
            candidate_id TEXT PRIMARY KEY, crop_path TEXT, crop_sha256 TEXT);
        CREATE TABLE table_reviews (review_id TEXT PRIMARY KEY, crop_sha256 TEXT);
        CREATE TABLE extraction_runs (run_id TEXT PRIMARY KEY, finished_at TEXT);
    """)
    conn.commit()


def _rmdir_if_empty(path: Path) -> None:
    """Remove the shared container once the last case has cleaned up its own."""
    try:
        path.rmdir()
    except OSError:
        pass


class GCFixture(unittest.TestCase):
    """A throwaway derived tree, store and snapshot dir inside workspace/."""

    def setUp(self):
        # Inside workspace/ because `ensure_writable` refuses anything outside
        # it -- the guard applies to tests too. `workspace/tests/` is TRACKED,
        # so the container directory is removed as well when this run empties
        # it: leaving `workspace/tests/gc/` behind dirties a tracked tree for
        # no content reason, which is the G28 failure in miniature.
        base = TESTS_DIR / "gc"
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="gc-", dir=base))
        self.addCleanup(_rmdir_if_empty, base)
        self.derived = self.tmp / "derived"
        self.derived.mkdir()
        self.snapshots = self.tmp / "snapshots"
        self.snapshots.mkdir()
        self.catalog = self.tmp / "catalog"
        self.catalog.mkdir()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        _schema(self.conn)
        self.addCleanup(self.conn.close)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def rel(self, p: Path) -> str:
        """Repo-relative, the form every path column in the store holds."""
        return os.path.relpath(Path(p).resolve(), ROOT)

    def scan(self, **kw):
        kw.setdefault("derived_dir", self.derived)
        kw.setdefault("snapshot_dir", self.snapshots)
        kw.setdefault("text_roots", (self.catalog,))
        return gcmod.collect(self.conn, **kw)

    def paths_of(self, report) -> set:
        return {o["path"] for o in report["orphans"]}


class TestDryRun(GCFixture):

    def test_orphan_is_reported_and_not_deleted(self):
        orphan = _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        report = self.scan()
        self.assertFalse(report["applied"])
        self.assertEqual(report["orphan_files"], 1)
        self.assertEqual(report["orphan_bytes"], orphan.stat().st_size)
        self.assertIn(self.rel(orphan), self.paths_of(report))
        self.assertEqual(report["deleted_files"], 0)
        self.assertTrue(orphan.is_file(), "a dry run must not delete anything")

    def test_dry_run_is_the_default(self):
        _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        report = gcmod.collect(self.conn, derived_dir=self.derived,
                               snapshot_dir=self.snapshots,
                               text_roots=(self.catalog,))
        self.assertFalse(report["applied"])
        self.assertEqual(report["deleted_files"], 0)

    def test_before_and_after_totals_are_reported(self):
        _write(self.derived / "doc-aaaa" / "pages" / "0001.png", b"12345")
        report = self.scan()
        self.assertEqual(report["before"]["files"], 1)
        self.assertEqual(report["before"]["bytes"], 5)
        # A dry run projects the after-state; it does not change it.
        self.assertEqual(report["after"]["files"], 0)
        self.assertEqual(report["after"]["bytes"], 0)


class TestApply(GCFixture):

    def test_apply_deletes_exactly_the_orphans(self):
        keep = _write(self.derived / "doc-aaaa" / "pages" / "0001.png", b"keep")
        drop = _write(self.derived / "doc-aaaa" / "pages" / "0002.png", b"drop-me")
        self.conn.execute("INSERT INTO pages VALUES ('p1', ?)", (self.rel(keep),))
        self.conn.commit()

        report = self.scan(apply=True)
        self.assertTrue(report["applied"])
        self.assertEqual(report["deleted_files"], 1)
        self.assertEqual(report["deleted_bytes"], len(b"drop-me"))
        self.assertTrue(keep.is_file())
        self.assertFalse(drop.exists())
        self.assertEqual(report["after"]["files"], 1)
        self.assertEqual(report["after"]["bytes"], len(b"keep"))

    def test_apply_prunes_the_directories_it_emptied(self):
        _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        self.scan(apply=True)
        self.assertFalse((self.derived / "doc-aaaa").exists())
        self.assertTrue(self.derived.is_dir(), "the derived root itself stays")

    def test_rerunning_apply_is_a_no_op(self):
        _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        self.scan(apply=True)
        again = self.scan(apply=True)
        self.assertEqual(again["orphan_files"], 0)
        self.assertEqual(again["deleted_files"], 0)


class TestReachability(GCFixture):
    """Every column that names a derived file is a root. None may be collected."""

    def _kept_by(self, insert_sql, path: Path):
        self.conn.execute(insert_sql, (self.rel(path),))
        self.conn.commit()
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(path.is_file())
        return report

    def test_page_image_row_keeps_its_file(self):
        p = _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        r = self._kept_by("INSERT INTO pages VALUES ('p1', ?)", p)
        self.assertEqual(r["roots"]["pages.page_image_path"], 1)

    def test_element_region_row_keeps_its_file(self):
        p = _write(self.derived / "doc-aaaa" / "regions" / "p0001-0002-figure.png")
        r = self._kept_by("INSERT INTO elements VALUES ('e1', ?)", p)
        self.assertEqual(r["roots"]["elements.region_image_path"], 1)

    def test_asset_row_keeps_its_file(self):
        p = _write(self.derived / "doc-aaaa" / "regions" / "p0003-0001-table.png")
        r = self._kept_by("INSERT INTO assets VALUES ('a1', ?)", p)
        self.assertEqual(r["roots"]["assets.path"], 1)

    def test_candidate_crop_row_keeps_its_file(self):
        p = _write(self.derived / "crops" / REF_A[:2] / f"{REF_A}-200-{FP}.png")
        self.conn.execute(
            "INSERT INTO table_read_candidates VALUES ('c1', ?, NULL)",
            (self.rel(p),))
        self.conn.commit()
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(p.is_file())

    def test_crop_a_human_reviewed_is_kept_by_its_digest(self):
        """`table_reviews` records a digest and no path. D6: the one verifiable
        claim in a review is *this person looked at these bytes*."""
        body = b"the image a reviewer saw"
        p = _write(self.derived / "crops" / "ab" / f"abababababababab-200-{FP}.png", body)
        self.conn.execute("INSERT INTO table_reviews VALUES ('r1', ?)",
                          (hashlib.sha256(body).hexdigest(),))
        self.conn.commit()
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(p.is_file())
        self.assertEqual(report["roots"]["review_crop_sha256"], 1)

    def test_a_text_reference_in_the_catalog_keeps_a_file(self):
        p = _write(self.derived / "doc-aaaa" / "table-candidates" / "p0006.png")
        (self.catalog / "noa-table-candidates.jsonl").write_text(
            json.dumps({"crop_path": self.rel(p)}) + "\n")
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(p.is_file())

    def test_unmanaged_subtrees_are_never_collected(self):
        """The collector owns page/region/table-candidate/crop images. Anything
        else under derived/ -- a tool checkout, a readings jsonl -- is out of
        scope, not garbage."""
        tool = _write(self.derived / "visualization-tools" / "node_modules" / "x.js")
        loose = _write(self.derived / "noa-engine-readings.jsonl", b"{}\n")
        stray = _write(self.derived / "doc-aaaa" / "notes" / "scratch.txt")
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertEqual(report["unmanaged_files"], 3)
        for p in (tool, loose, stray):
            self.assertTrue(p.is_file(), p)

    def test_a_symlink_is_skipped_never_followed(self):
        target = _write(self.tmp / "outside.png")
        link = self.derived / "doc-aaaa" / "pages" / "0001.png"
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, link)
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0)
        self.assertEqual(len(report["symlinks_skipped"]), 1)
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.is_file())


class TestPublishedSnapshots(GCFixture):
    """Obligation 3: a published citation must keep resolving, forever."""

    def _publish(self, payload: dict, sid="a" * 64):
        (self.snapshots / f"{sid}.json").write_text(json.dumps(payload))

    def test_crop_cited_by_a_published_snapshot_is_never_collected(self):
        p = _write(self.derived / "crops" / REF_A[:2] / f"{REF_A}-200-{FP}.png")
        self._publish({"snapshot_id": "a" * 64, "warnings": [
            {"code": "X", "cites": [{"id": REF_A, "belongs_to": "f" * 64}]}]})
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(p.is_file())
        self.assertEqual(report["roots"]["published_snapshot_cites"], 1)

    def test_every_dpi_and_fingerprint_of_a_cited_ref_is_kept(self):
        """The cache key carries dpi and a toolchain fingerprint; the citation
        carries neither, so the ref id is what has to be honoured."""
        a = _write(self.derived / "crops" / REF_A[:2] / f"{REF_A}-200-{FP}.png")
        b = _write(self.derived / "crops" / REF_A[:2] / f"{REF_A}-600-deadbeef.png")
        self._publish({"parameters": [{"id": REF_A, "belongs_to": "f" * 64}]})
        self.scan(apply=True)
        self.assertTrue(a.is_file())
        self.assertTrue(b.is_file())

    def test_a_cite_outside_warnings_still_roots(self):
        p = _write(self.derived / "crops" / REF_B[:2] / f"{REF_B}-200-{FP}.png")
        self._publish({"rules": [{"because": {"cites": [{"id": REF_B}]}}]})
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0, report["orphans"])
        self.assertTrue(p.is_file())

    def test_an_uncited_crop_is_collectable(self):
        """The counterweight: without it the two tests above would pass on a
        collector that simply never collects a crop."""
        p = _write(self.derived / "crops" / REF_B[:2] / f"{REF_B}-200-{FP}.png")
        self._publish({"warnings": [{"cites": [{"id": REF_A, "belongs_to": "f" * 64}]}]})
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 1)
        self.assertFalse(p.exists())

    def test_a_gap_id_is_not_mistaken_for_a_citation(self):
        """`Gap` is `(id, kind, subject, ...)` with no `belongs_to` and no
        `cites` parent -- 63 of them in the shipped snapshot. Treating those as
        cites would not be unsafe, but it would silently inflate the root set."""
        self._publish({"gaps": [{"id": REF_B, "kind": "missing", "subject": "x"}]})
        report = self.scan()
        self.assertEqual(report["roots"]["published_snapshot_cites"], 0)

    def test_an_unreadable_snapshot_stops_the_collection(self):
        """A snapshot we cannot parse may cite anything. Refuse to collect
        rather than guess."""
        _write(self.derived / "crops" / REF_B[:2] / f"{REF_B}-200-{FP}.png")
        (self.snapshots / "broken.json").write_text("{not json")
        report = self.scan(apply=True)
        self.assertTrue(report["unsafe"])
        self.assertEqual(report["deleted_files"], 0)
        self.assertTrue(report["unreadable_snapshots"])


class TestGuards(GCFixture):

    def test_a_derived_dir_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="gc-outside-"))
        self.addCleanup(shutil.rmtree, outside, True)
        _write(outside / "doc-aaaa" / "pages" / "0001.png")
        with self.assertRaises(CorpusWriteError):
            gcmod.collect(self.conn, derived_dir=outside,
                          snapshot_dir=self.snapshots, text_roots=())

    def test_the_corpus_itself_is_refused(self):
        with self.assertRaises(CorpusWriteError):
            gcmod.collect(self.conn, derived_dir=ROOT / "manuals",
                          snapshot_dir=self.snapshots, text_roots=())

    def test_deleting_a_path_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="gc-outside-"))
        self.addCleanup(shutil.rmtree, outside, True)
        victim = _write(outside / "keepme.png")
        with self.assertRaises(CorpusWriteError):
            gcmod.remove_derived_file(victim)
        self.assertTrue(victim.is_file())

    def test_a_dotdot_out_of_the_derived_tree_is_refused(self):
        """`ensure_writable` is necessary and not sufficient. It asserts only
        "somewhere under workspace/", which a `..` satisfies while walking
        straight out of the derived store — into `workspace/indexes/evidence.db`
        or, worse, `workspace/snapshots/`, the one thing here that cannot be
        regenerated. Verified before the fix: this deleted the store."""
        victim = _write(self.tmp / "indexes" / "evidence.db")
        escape = self.derived / ".." / "indexes" / "evidence.db"
        with self.assertRaises(CorpusWriteError):
            gcmod.remove_derived_file(escape, self.derived)
        self.assertTrue(victim.is_file())

    def test_a_snapshot_beside_the_derived_tree_is_refused(self):
        victim = _write(self.snapshots / "deadbeef.json")
        with self.assertRaises(CorpusWriteError):
            gcmod.remove_derived_file(victim, self.derived)
        self.assertTrue(victim.is_file())

    def test_a_file_inside_the_derived_tree_is_deleted(self):
        """The guard must not be a blanket refusal."""
        doomed = _write(self.derived / "doc-aaaa" / "pages" / "0001.png")
        gcmod.remove_derived_file(doomed, self.derived)
        self.assertFalse(doomed.exists())

    def test_an_unfinished_extraction_run_stops_the_collection(self):
        """`ingest` renders every page image and region crop in a worker and
        commits the rows only when the parent consumes the future, so with 10
        workers there are always ~9 documents' worth of PNGs on disk that no
        row names yet. Deleting a region crop is not recoverable: `get_region`
        re-crops only when the column is NULL, never when it names a file that
        is gone."""
        orphan = _write(self.derived / "doc-aaaa" / "regions" / "p1-0-x.png")
        self.conn.execute(
            "INSERT INTO extraction_runs(run_id, finished_at) VALUES ('run-1', NULL)")
        self.conn.commit()
        report = self.scan(apply=True)
        self.assertTrue(report["unsafe"])
        self.assertEqual(report["runs_in_flight"], ["run-1"])
        self.assertEqual(report["deleted_files"], 0)
        self.assertTrue(orphan.is_file())

    def test_a_finished_run_does_not_stop_it(self):
        _write(self.derived / "doc-aaaa" / "regions" / "p1-0-x.png")
        self.conn.execute("INSERT INTO extraction_runs(run_id, finished_at) "
                          "VALUES ('run-1', '2026-01-01T00:00:00Z')")
        self.conn.commit()
        report = self.scan(apply=True)
        self.assertFalse(report["unsafe"])
        self.assertEqual(report["deleted_files"], 1)

    def test_a_file_written_after_the_roots_were_read_is_kept(self):
        """The clock half of the race. A file younger than the root read cannot
        be judged against roots that predate it."""
        import time as _t
        fresh = _write(self.derived / "doc-aaaa" / "regions" / "p1-0-x.png")
        os.utime(fresh, (_t.time() + 3600, _t.time() + 3600))
        report = self.scan(apply=True)
        self.assertEqual(report["too_young_to_judge"], 1)
        self.assertEqual(report["orphan_files"], 0)
        self.assertTrue(fresh.is_file())

    def test_a_row_committed_during_the_walk_saves_its_file(self):
        """The half a clock cannot cover. `collect` re-reads the path roots
        before deleting, so a row that landed mid-walk still rescues its file."""
        victim = _write(self.derived / "doc-aaaa" / "regions" / "p1-0-x.png")
        real_walk = gcmod.os.walk
        conn = self.conn
        rel = self.rel

        def walk_then_commit(*a, **kw):
            out = list(real_walk(*a, **kw))
            conn.execute("INSERT INTO elements(element_id, region_image_path) "
                         "VALUES ('e1', ?)", (rel(victim),))
            conn.commit()
            return iter(out)

        gcmod.os.walk = walk_then_commit
        try:
            report = self.scan(apply=True)
        finally:
            gcmod.os.walk = real_walk
        self.assertEqual(report["orphan_files"], 1)
        self.assertEqual(report["became_reachable"], 1)
        self.assertEqual(report["deleted_files"], 0)
        self.assertTrue(victim.is_file())

    def test_a_missing_snapshot_directory_is_unsafe_not_empty(self):
        """Absent is not "no snapshots exist": `workspace/snapshots/` is tracked
        in git, so its absence means a sparse or partial tree — and then every
        cached crop of every published citation reads as an orphan."""
        _write(self.derived / "crops" / "aa" / "aaaaaaaaaaaaaaaa-200-ff.png")
        shutil.rmtree(self.snapshots)
        report = self.scan(apply=True)
        self.assertTrue(report["unsafe"])
        self.assertEqual(report["deleted_files"], 0)

    def test_an_empty_derived_store_is_a_no_op(self):
        report = self.scan(apply=True)
        self.assertEqual(report["before"], {"files": 0, "bytes": 0})
        self.assertEqual(report["orphan_files"], 0)
        self.assertEqual(report["deleted_files"], 0)
        self.assertEqual(report["orphans"], [])
        self.assertFalse(report["unsafe"])

    def test_a_missing_derived_store_is_a_no_op(self):
        shutil.rmtree(self.derived)
        report = self.scan(apply=True)
        self.assertEqual(report["orphan_files"], 0)
        self.assertEqual(report["deleted_files"], 0)


class TestCLI(unittest.TestCase):

    def test_gc_is_a_documented_verb(self):
        from fence_evidence import cli
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["--help"])
        self.assertIn("gc", buf.getvalue())

    def test_gc_help_names_the_dry_run_default(self):
        from fence_evidence import cli
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit):
            cli.main(["gc", "--help"])
        text = buf.getvalue()
        self.assertIn("--apply", text)
        self.assertIn("--derived", text)


if __name__ == "__main__":
    unittest.main()
