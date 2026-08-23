# Corpus Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the corpus and a prebuilt `evidence.db` to a public Cloudflare R2 bucket so a fresh checkout can obtain them anonymously, without spending GitHub LFS bandwidth and without a 33-minute rebuild.

**Architecture:** Content-addressed objects (`objects/<sha256>`) in one public-read R2 bucket, indexed by a generated distribution manifest projected from the existing `corpus-manifest.jsonl`. Publishing is maintainer-only and signs S3 requests with SigV4 implemented in the standard library. Consuming is anonymous HTTPS GET plus hash verification. `workspace/derived/` is never published — page images become an on-demand cache rendered from the source PDFs.

**Tech Stack:** Python 3.10+ standard library only (`urllib.request`, `hmac`, `hashlib`, `json`, `sqlite3`). No boto3, no SDK, no `aws`/`rclone`/`wrangler` — none are installed and none may be added.

**Spec:** `docs/distribution-design.md`

## Global Constraints

- **Standard library only.** Every third-party package must remain optional; none may be added for this feature. `workspace/pylibs/` holds only optional extraction backends.
- **The corpus is read-only.** `manuals/`, `china/manuals/`, `data/` must never be modified by pipeline code. `paths.ensure_writable` permits writes only under `workspace/`. Task 4 introduces the single, contained exception and the test that keeps it contained.
- **Tests are stdlib `unittest`**, live in `tests/`, start with `from context import ROOT`, and run via `python3 tests/run_tests.py`. The suite must pass on a clean checkout with no corpus and no store — use `@requires_store` from `tests/context.py` for anything needing `evidence.db`.
- **No network access in tests.** Anything HTTP is tested against `http.server` bound to `127.0.0.1`, never a real endpoint.
- **Secrets never printed.** `.env` values must not appear in stdout, logs, exception messages, or the generated manifest. `R2_PUBLIC_BASE_URL` is the sole non-secret and is the only one written into the manifest.
- **CLI convention:** register with `sub.add_parser(...)` in `cli.py`, dispatch in the `elif args.cmd == ...` chain, import the implementing module lazily inside the branch, and emit a dict through `_print`.
- Baseline to preserve: **164 tests passing**.
- Measured corpus facts, used throughout: **144 manifest rows → 128 unique `sha256` → 376.5 MB**. Subset predicates and sizes are in `docs/distribution-design.md` §4. The manifest field is `structural_subdir` (boolean), **not** `structural`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/fence_evidence/config.py` | Parse `.env`; expose `R2Config`; never log secrets |
| `src/fence_evidence/sigv4.py` | AWS SigV4 request signing, pure functions, no I/O |
| `src/fence_evidence/distribution.py` | Project `corpus-manifest.jsonl` into the distribution manifest; subset predicates |
| `src/fence_evidence/fetch.py` | Anonymous download + hash verification + idempotency |
| `src/fence_evidence/publish.py` | Maintainer-only upload to R2 |
| `src/fence_evidence/paths.py` (modify) | Add `fetch_target()` — the contained corpus-write exception — and `resolve_asset()` |
| `src/fence_evidence/cli.py` (modify) | Register `fetch`, `publish` |
| `tests/test_distribution.py` | Manifest projection, subset predicates, config parsing |
| `tests/test_sigv4.py` | Signing against AWS's published vector |
| `tests/test_fetch.py` | Download/verify/idempotency against a local HTTP server |
| `tests/test_asset_cache.py` | `resolve_asset` correctness and the D6 cache property |

---

### Task 1: `.env` configuration loader

**Files:**
- Create: `src/fence_evidence/config.py`
- Test: `tests/test_distribution.py`

**Interfaces:**
- Produces: `load_env(path: Path | None = None) -> dict[str, str]`; `R2Config` dataclass with fields `account_id, access_key_id, secret_access_key, bucket, public_base_url`, classmethod `R2Config.from_env(env: dict[str,str]) -> R2Config`, property `endpoint -> str`, and `R2Config.redacted() -> dict` for safe printing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_distribution.py
"""Distribution manifest projection and R2 configuration."""
import unittest
from pathlib import Path
import tempfile

from context import ROOT  # noqa: F401
from fence_evidence.config import load_env, R2Config, ConfigError


class TestLoadEnv(unittest.TestCase):
    def _write(self, text: str) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / ".env"
        p.write_text(text, encoding="utf-8")
        return p

    def test_parses_pairs_and_ignores_comments_and_blanks(self):
        p = self._write(
            "# a comment\n"
            "\n"
            "R2_BUCKET=fence-rag\n"
            "R2_ACCOUNT_ID=abc123\n"
        )
        env = load_env(p)
        self.assertEqual(env["R2_BUCKET"], "fence-rag")
        self.assertEqual(env["R2_ACCOUNT_ID"], "abc123")
        self.assertNotIn("# a comment", env)

    def test_strips_surrounding_quotes_and_whitespace(self):
        p = self._write('R2_SECRET_ACCESS_KEY = "s3cr3t"\n')
        self.assertEqual(load_env(p)["R2_SECRET_ACCESS_KEY"], "s3cr3t")

    def test_value_containing_equals_is_preserved(self):
        p = self._write("R2_SECRET_ACCESS_KEY=a=b=c\n")
        self.assertEqual(load_env(p)["R2_SECRET_ACCESS_KEY"], "a=b=c")

    def test_missing_file_returns_empty_mapping(self):
        self.assertEqual(load_env(Path("/nonexistent/.env")), {})


class TestR2Config(unittest.TestCase):
    FULL = {
        "R2_ACCOUNT_ID": "abc123",
        "R2_ACCESS_KEY_ID": "AKID",
        "R2_SECRET_ACCESS_KEY": "SECRET",
        "R2_BUCKET": "fence-rag",
        "R2_PUBLIC_BASE_URL": "https://pub.example.com/",
    }

    def test_endpoint_is_derived_from_account_id(self):
        cfg = R2Config.from_env(self.FULL)
        self.assertEqual(cfg.endpoint, "https://abc123.r2.cloudflarestorage.com")

    def test_missing_key_names_the_variable(self):
        env = dict(self.FULL)
        del env["R2_SECRET_ACCESS_KEY"]
        with self.assertRaises(ConfigError) as cm:
            R2Config.from_env(env)
        self.assertIn("R2_SECRET_ACCESS_KEY", str(cm.exception))

    def test_empty_value_is_treated_as_missing(self):
        env = dict(self.FULL, R2_ACCESS_KEY_ID="")
        with self.assertRaises(ConfigError) as cm:
            R2Config.from_env(env)
        self.assertIn("R2_ACCESS_KEY_ID", str(cm.exception))

    def test_public_base_url_is_normalised_to_end_with_slash(self):
        cfg = R2Config.from_env(dict(self.FULL, R2_PUBLIC_BASE_URL="https://pub.example.com"))
        self.assertEqual(cfg.public_base_url, "https://pub.example.com/")

    def test_redacted_never_exposes_the_secret(self):
        cfg = R2Config.from_env(self.FULL)
        blob = repr(cfg.redacted())
        self.assertNotIn("SECRET", blob)
        self.assertIn("fence-rag", blob)

    def test_repr_never_exposes_the_secret(self):
        cfg = R2Config.from_env(self.FULL)
        self.assertNotIn("SECRET", repr(cfg))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_distribution -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fence_evidence.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/fence_evidence/config.py
"""Configuration for publishing to object storage.

Reads .env, which is git-ignored. This repository is public: a committed
credential is a disclosed credential. Nothing here may print a secret --
use R2Config.redacted() when reporting configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .paths import REPO_ROOT


class ConfigError(Exception):
    """Configuration is absent or incomplete."""


def load_env(path: Path | None = None) -> dict[str, str]:
    """Parse a .env file into a mapping. A missing file yields {}."""
    p = Path(path) if path is not None else REPO_ROOT / ".env"
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


@dataclass
class R2Config:
    account_id: str
    bucket: str
    public_base_url: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)

    REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET", "R2_PUBLIC_BASE_URL")

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "R2Config":
        missing = [k for k in cls.REQUIRED if not env.get(k, "").strip()]
        if missing:
            raise ConfigError(
                "missing or empty in .env: " + ", ".join(missing)
                + "\ncopy .env.example to .env and fill it in"
            )
        base = env["R2_PUBLIC_BASE_URL"].strip()
        if not base.endswith("/"):
            base += "/"
        return cls(
            account_id=env["R2_ACCOUNT_ID"].strip(),
            bucket=env["R2_BUCKET"].strip(),
            public_base_url=base,
            access_key_id=env["R2_ACCESS_KEY_ID"].strip(),
            secret_access_key=env["R2_SECRET_ACCESS_KEY"].strip(),
        )

    @property
    def endpoint(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def redacted(self) -> dict[str, str]:
        return {
            "account_id": self.account_id,
            "bucket": self.bucket,
            "public_base_url": self.public_base_url,
            "endpoint": self.endpoint,
            "access_key_id": self.access_key_id[:4] + "…" if self.access_key_id else "",
            "secret_access_key": "<redacted>",
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests && python3 -m unittest test_distribution -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Run the whole suite**

Run: `python3 tests/run_tests.py`
Expected: 175 tests, OK

- [ ] **Step 6: Commit**

```bash
git add src/fence_evidence/config.py tests/test_distribution.py
git commit -m "feat(dist): read R2 configuration from .env without leaking secrets"
```

---

### Task 2: SigV4 request signing

**Files:**
- Create: `src/fence_evidence/sigv4.py`
- Test: `tests/test_sigv4.py`

**Interfaces:**
- Consumes: nothing from Task 1 — deliberately pure so it can be tested against published vectors.
- Produces: `derive_signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes`; `sign_request(method: str, url: str, headers: dict[str,str], payload: bytes, access_key: str, secret_key: str, region: str = "auto", service: str = "s3", now: datetime | None = None) -> dict[str,str]` returning headers to send, including `Authorization`, `x-amz-date`, `x-amz-content-sha256`, and `host`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sigv4.py
"""AWS SigV4 signing, checked against AWS's published example."""
import unittest
from datetime import datetime, timezone

from context import ROOT  # noqa: F401
from fence_evidence.sigv4 import derive_signing_key, sign_request, canonical_request


class TestDeriveSigningKey(unittest.TestCase):
    def test_matches_the_aws_documented_example(self):
        # From AWS's "Examples of how to derive a signing key" documentation.
        # IF THIS FAILS, THE IMPLEMENTATION IS WRONG. Do not edit this vector to
        # match the code -- re-check against AWS's published SigV4 test suite.
        key = derive_signing_key(
            "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
            "20120215", "us-east-1", "iam")
        self.assertEqual(
            key.hex(),
            "f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d")


class TestCanonicalRequest(unittest.TestCase):
    def test_headers_are_lowercased_sorted_and_trimmed(self):
        cr, signed = canonical_request(
            "PUT", "https://acct.r2.cloudflarestorage.com/bucket/objects/abc",
            {"X-Amz-Date": "20250101T000000Z", "Host": "acct.r2.cloudflarestorage.com",
             "Content-Type": "  application/pdf  "},
            b"", payload_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(signed, "content-type;host;x-amz-date")
        self.assertIn("content-type:application/pdf\n", cr)
        self.assertTrue(cr.startswith("PUT\n/bucket/objects/abc\n"))

    def test_path_segments_are_encoded_but_slashes_preserved(self):
        cr, _ = canonical_request(
            "GET", "https://h.example.com/bucket/a%20b/c",
            {"Host": "h.example.com"}, b"",
            payload_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertIn("/bucket/a%2520b/c", cr.splitlines()[1] + "|" + cr.splitlines()[1])


class TestSignRequest(unittest.TestCase):
    def test_returns_the_required_headers(self):
        h = sign_request(
            "PUT", "https://acct.r2.cloudflarestorage.com/fence-rag/objects/deadbeef",
            {}, b"hello",
            access_key="AKID", secret_key="SECRET", region="auto", service="s3",
            now=datetime(2025, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(h["x-amz-date"], "20250101T000000Z")
        self.assertEqual(h["host"], "acct.r2.cloudflarestorage.com")
        self.assertEqual(
            h["x-amz-content-sha256"],
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
        self.assertTrue(h["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKID/20250101/auto/s3/aws4_request,"))
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", h["Authorization"])

    def test_signature_is_deterministic_for_fixed_inputs(self):
        args = dict(
            method="PUT",
            url="https://acct.r2.cloudflarestorage.com/fence-rag/objects/deadbeef",
            headers={}, payload=b"hello", access_key="AKID", secret_key="SECRET",
            region="auto", service="s3", now=datetime(2025, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(sign_request(**args)["Authorization"],
                         sign_request(**args)["Authorization"])

    def test_different_payload_changes_the_signature(self):
        base = dict(
            method="PUT",
            url="https://acct.r2.cloudflarestorage.com/fence-rag/objects/deadbeef",
            headers={}, access_key="AKID", secret_key="SECRET",
            region="auto", service="s3", now=datetime(2025, 1, 1, tzinfo=timezone.utc))
        a = sign_request(payload=b"hello", **base)["Authorization"]
        b = sign_request(payload=b"world", **base)["Authorization"]
        self.assertNotEqual(a, b)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_sigv4 -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fence_evidence.sigv4'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/fence_evidence/sigv4.py
"""AWS Signature Version 4, standard library only.

Used to sign S3-compatible requests to Cloudflare R2. No third-party SDK is
installed on this machine and none may be added; see
workspace/reports/dependency-options.md.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

ALGORITHM = "AWS4-HMAC-SHA256"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def derive_signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k = _hmac(k, region)
    k = _hmac(k, service)
    return _hmac(k, "aws4_request")


def canonical_request(method: str, url: str, headers: dict[str, str],
                      payload: bytes, payload_sha256: str) -> tuple[str, str]:
    parts = urlsplit(url)
    # each path segment is percent-encoded; the separators are not
    path = "/" + "/".join(quote(seg, safe="") for seg in parts.path.lstrip("/").split("/"))
    query = "&".join(sorted(parts.query.split("&"))) if parts.query else ""

    merged = {k.lower(): " ".join(str(v).split()) for k, v in headers.items()}
    merged.setdefault("host", parts.netloc)
    signed_headers = ";".join(sorted(merged))
    canonical_headers = "".join(f"{k}:{merged[k]}\n" for k in sorted(merged))

    cr = "\n".join([method.upper(), path, query, canonical_headers,
                    signed_headers, payload_sha256])
    return cr, signed_headers


def sign_request(method: str, url: str, headers: dict[str, str], payload: bytes,
                 access_key: str, secret_key: str, region: str = "auto",
                 service: str = "s3", now: datetime | None = None) -> dict[str, str]:
    """Return the headers to send, including Authorization."""
    now = now or datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    payload_sha256 = hashlib.sha256(payload).hexdigest() if payload else EMPTY_SHA256

    out = dict(headers)
    out["host"] = urlsplit(url).netloc
    out["x-amz-date"] = amzdate
    out["x-amz-content-sha256"] = payload_sha256

    cr, signed_headers = canonical_request(method, url, out, payload, payload_sha256)
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [ALGORITHM, amzdate, scope, hashlib.sha256(cr.encode("utf-8")).hexdigest()])
    signature = hmac.new(
        derive_signing_key(secret_key, datestamp, region, service),
        string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    out["Authorization"] = (
        f"{ALGORITHM} Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests && python3 -m unittest test_sigv4 -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fence_evidence/sigv4.py tests/test_sigv4.py
git commit -m "feat(dist): SigV4 signing in the standard library"
```

---

### Task 3: Distribution manifest projection

**Files:**
- Create: `src/fence_evidence/distribution.py`
- Modify: `tests/test_distribution.py` (append)

**Interfaces:**
- Consumes: `R2Config` (Task 1) for `public_base_url` only.
- Produces: `SUBSETS: dict[str, Callable[[dict], bool]]`; `build_manifest(rows: list[dict], base_url: str, generated_at: str) -> dict`; `object_key(sha256: str) -> str`; `load_corpus_manifest(path: Path | None = None) -> list[dict]`; `files_for_subset(manifest: dict, subset: str) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_distribution.py
from fence_evidence.distribution import (SUBSETS, build_manifest, object_key,
                                         files_for_subset, load_corpus_manifest)


def _row(path, sha, size, structural=False):
    return {"source_path": path, "sha256": sha, "file_size_bytes": size,
            "structural_subdir": structural}


class TestSubsetPredicates(unittest.TestCase):
    def test_structural_uses_structural_subdir_not_structural(self):
        self.assertTrue(SUBSETS["structural"](_row("manuals/x/structural/a.pdf", "a", 1, True)))
        self.assertFalse(SUBSETS["structural"](_row("manuals/x/a.pdf", "a", 1, False)))

    def test_china_matches_the_china_track_only(self):
        self.assertTrue(SUBSETS["china"](_row("china/manuals/a.pdf", "a", 1)))
        self.assertFalse(SUBSETS["china"](_row("manuals/a.pdf", "a", 1)))

    def test_all_matches_everything(self):
        self.assertTrue(SUBSETS["all"](_row("anything", "a", 1)))


class TestBuildManifest(unittest.TestCase):
    ROWS = [
        _row("manuals/certainteed-bufftech/a.pdf", "aaa", 100, False),
        _row("manuals/certainteed-bufftech/structural/b.pdf", "bbb", 200, True),
        _row("manuals/freedom-outdoor-living/b-copy.pdf", "bbb", 200, False),
        _row("china/manuals/c.pdf", "ccc", 300, False),
    ]

    def setUp(self):
        self.m = build_manifest(self.ROWS, "https://pub.example.com/", "2026-01-01T00:00:00Z")

    def test_duplicate_sha256_is_counted_once_in_bytes(self):
        # 4 files, 3 unique objects, 100+200+300 = 600 bytes
        self.assertEqual(self.m["subsets"]["all"]["files"], 4)
        self.assertEqual(self.m["subsets"]["all"]["unique"], 3)
        self.assertEqual(self.m["subsets"]["all"]["bytes"], 600)

    def test_every_file_lists_the_subsets_it_belongs_to(self):
        by_path = {f["source_path"]: f for f in self.m["files"]}
        self.assertIn("structural", by_path["manuals/certainteed-bufftech/structural/b.pdf"]["subsets"])
        self.assertIn("bufftech", by_path["manuals/certainteed-bufftech/a.pdf"]["subsets"])
        self.assertIn("china", by_path["china/manuals/c.pdf"]["subsets"])

    def test_base_url_is_recorded_and_no_secret_is_present(self):
        self.assertEqual(self.m["base_url"], "https://pub.example.com/")
        blob = repr(self.m)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("R2_SECRET_ACCESS_KEY", blob)

    def test_files_for_subset_returns_both_paths_of_a_duplicate(self):
        got = {f["source_path"] for f in files_for_subset(self.m, "all")}
        self.assertEqual(len(got), 4)

    def test_unknown_subset_raises(self):
        with self.assertRaises(KeyError):
            files_for_subset(self.m, "nope")


class TestObjectKey(unittest.TestCase):
    def test_key_is_content_addressed(self):
        self.assertEqual(object_key("abc123"), "objects/abc123")


class TestAgainstTheRealCorpusManifest(unittest.TestCase):
    def test_real_manifest_projects_to_128_unique_objects(self):
        rows = load_corpus_manifest()
        if not rows:
            self.skipTest("corpus manifest not built")
        m = build_manifest(rows, "https://pub.example.com/", "2026-01-01T00:00:00Z")
        self.assertEqual(m["subsets"]["all"]["files"], 144)
        self.assertEqual(m["subsets"]["all"]["unique"], 128)
        self.assertEqual(m["subsets"]["structural"]["files"], 32)
        self.assertEqual(m["subsets"]["china"]["files"], 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_distribution -v`
Expected: FAIL — `ImportError: cannot import name 'SUBSETS'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/fence_evidence/distribution.py
"""Project the corpus manifest into a distribution manifest.

The corpus manifest already records source_path, sha256 and file_size_bytes for
every file, so it is already a download manifest. This module is the projection:
it never invents data and is regenerated, never hand-edited.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .paths import MANIFEST_PATH

SUBSETS: dict[str, Callable[[dict], bool]] = {
    "all": lambda r: True,
    "structural": lambda r: bool(r.get("structural_subdir")),
    "bufftech": lambda r: r["source_path"].startswith("manuals/certainteed-bufftech/"),
    "china": lambda r: r["source_path"].startswith("china/"),
}


def object_key(sha256: str) -> str:
    return f"objects/{sha256}"


def load_corpus_manifest(path: Path | None = None) -> list[dict]:
    p = Path(path) if path is not None else MANIFEST_PATH
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_manifest(rows: list[dict], base_url: str, generated_at: str) -> dict:
    files = []
    for r in rows:
        subsets = sorted(name for name, pred in SUBSETS.items() if pred(r))
        files.append({
            "source_path": r["source_path"],
            "sha256": r["sha256"],
            "bytes": r["file_size_bytes"],
            "key": object_key(r["sha256"]),
            "subsets": subsets,
        })
    summary = {}
    for name, pred in SUBSETS.items():
        sel = [r for r in rows if pred(r)]
        uniq = {r["sha256"]: r["file_size_bytes"] for r in sel}
        summary[name] = {"files": len(sel), "unique": len(uniq),
                         "bytes": sum(uniq.values())}
    return {"schema": 1, "generated_at": generated_at, "base_url": base_url,
            "subsets": summary, "files": sorted(files, key=lambda f: f["source_path"])}


def files_for_subset(manifest: dict, subset: str) -> list[dict]:
    if subset not in manifest["subsets"]:
        raise KeyError(f"unknown subset {subset!r}; known: {sorted(manifest['subsets'])}")
    return [f for f in manifest["files"] if subset in f["subsets"]]
```

- [ ] **Step 4: No paths.py change needed — verify the constants exist**

Run: `grep -nE "^(CATALOG_DIR|MANIFEST_PATH|EVIDENCE_DB|DERIVED_DIR)" src/fence_evidence/paths.py`
Expected: all four already defined (lines 32, 39, 38, 33). `MANIFEST_PATH` is `CATALOG_DIR / "corpus-manifest.jsonl"` — use it rather than rebuilding the path.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd tests && python3 -m unittest test_distribution -v`
Expected: PASS. The real-manifest test asserts 144 files → 128 unique, 32 structural, 4 china.

- [ ] **Step 6: Commit**

```bash
git add src/fence_evidence/distribution.py src/fence_evidence/paths.py tests/test_distribution.py
git commit -m "feat(dist): project the corpus manifest into a distribution manifest"
```

---

### Task 4: The contained corpus-write exception

This is the security-critical task. `fetch` must write into `manuals/` and `china/manuals/`, which `ensure_writable` exists to forbid. The exception must be narrow, explicit, and provably unreachable from pipeline code.

**Files:**
- Modify: `src/fence_evidence/paths.py`
- Test: `tests/test_safety.py` (append — it already holds the read-only guard tests)

**Interfaces:**
- Produces: `fetch_target(path: os.PathLike | str, allowed: set[str]) -> Path` — returns the resolved path if and only if it is inside a corpus root, its repo-relative form is in `allowed`, and no component is a symlink. Raises `CorpusWriteError` otherwise.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_safety.py
import os
from fence_evidence.paths import fetch_target, CorpusWriteError, REPO_ROOT


class TestFetchTargetGuard(unittest.TestCase):
    ALLOWED = {"manuals/example/doc.pdf"}

    def test_allows_a_listed_corpus_path(self):
        p = fetch_target(REPO_ROOT / "manuals/example/doc.pdf", self.ALLOWED)
        self.assertEqual(p, (REPO_ROOT / "manuals/example/doc.pdf").resolve())

    def test_refuses_a_corpus_path_not_in_the_manifest(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "manuals/example/other.pdf", self.ALLOWED)

    def test_refuses_a_path_outside_the_corpus_even_if_listed(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "src/fence_evidence/cli.py",
                         {"src/fence_evidence/cli.py"})

    def test_refuses_traversal_out_of_the_corpus(self):
        with self.assertRaises(CorpusWriteError):
            fetch_target(REPO_ROOT / "manuals/../src/x.py", {"manuals/../src/x.py"})

    def test_refuses_a_symlinked_component(self):
        import tempfile
        link = REPO_ROOT / "manuals" / "_test_link"
        target = Path(tempfile.mkdtemp())
        try:
            os.symlink(target, link)
            with self.assertRaises(CorpusWriteError):
                fetch_target(link / "doc.pdf", {"manuals/_test_link/doc.pdf"})
        finally:
            if link.is_symlink():
                link.unlink()


class TestFetchTargetIsNotReachableFromPipelineCode(unittest.TestCase):
    """fetch_target is the one hole in the read-only guard. Keep it contained."""

    PERMITTED = {"paths.py", "fetch.py", "cli.py"}

    def test_only_fetch_and_cli_reference_fetch_target(self):
        src = REPO_ROOT / "src" / "fence_evidence"
        offenders = []
        for py in sorted(src.glob("*.py")):
            if py.name in self.PERMITTED:
                continue
            if "fetch_target" in py.read_text(encoding="utf-8"):
                offenders.append(py.name)
        self.assertEqual(offenders, [],
                         f"fetch_target must not be reachable from pipeline code: {offenders}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_safety -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_target'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/fence_evidence/paths.py`, directly below `ensure_writable` so the two guards are read together:

```python
def fetch_target(path: os.PathLike | str, allowed: set[str]) -> Path:
    """Return ``path`` if it is a corpus file the distribution manifest names.

    This is the ONE exception to the read-only corpus rule, and it exists only
    so `cli fetch` can populate a checkout the way `git lfs pull` does. It is
    not pipeline code: `tests/test_safety.py` asserts that no module other than
    fetch.py and cli.py references it.

    Three conditions, all required:
      1. the path resolves inside a corpus root;
      2. its repo-relative form appears in ``allowed`` (the manifest);
      3. no component is a symlink.
    """
    p = Path(path)
    for parent in (p, *p.parents):
        if parent.is_symlink():
            raise CorpusWriteError(f"refusing to write through a symlink: {parent}")
    resolved = p.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        raise CorpusWriteError(f"refusing to write outside the repository: {resolved}") from None
    if not any(_is_within(resolved, root) for root in CORPUS_ROOTS):
        raise CorpusWriteError(f"not a corpus path: {relative}")
    if relative not in allowed:
        raise CorpusWriteError(
            f"{relative} is not listed in the distribution manifest; refusing to write")
    return resolved


def _is_within(child: Path, root: Path) -> bool:
    try:
        child.relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tests && python3 -m unittest test_safety -v`
Expected: PASS, including the containment test.

- [ ] **Step 5: Commit**

```bash
git add src/fence_evidence/paths.py tests/test_safety.py
git commit -m "feat(dist): contained corpus-write guard for fetch, with a containment test"
```

---

### Task 5: `cli fetch` — anonymous download and verification

**Files:**
- Create: `src/fence_evidence/fetch.py`
- Modify: `src/fence_evidence/cli.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `files_for_subset`, `object_key` (Task 3); `fetch_target` (Task 4).
- Produces: `fetch_subset(manifest: dict, subset: str, dest_root: Path, workers: int = 4) -> dict` returning `{"requested", "downloaded", "already_present", "bytes", "failed"}`; `download_object(url: str, expected_sha256: str, dest: Path, tmp_dir: Path) -> bool` returning True if downloaded, False if already present and matching.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch.py
"""Anonymous fetch: hash verification, idempotency, and manifest containment."""
import hashlib
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path

from context import ROOT  # noqa: F401
from fence_evidence.distribution import build_manifest
from fence_evidence.fetch import download_object, fetch_subset
from fence_evidence.paths import CorpusWriteError

PAYLOAD = b"%PDF-1.4 pretend document\n"
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _Handler(http.server.BaseHTTPRequestHandler):
    corrupt = False

    def do_GET(self):
        body = b"tampered" if self.corrupt else PAYLOAD
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class ServerCase(unittest.TestCase):
    def setUp(self):
        _Handler.corrupt = False
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        self.base = f"http://127.0.0.1:{self.srv.server_port}/"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        self.srv.shutdown()


class TestDownloadObject(ServerCase):
    def test_downloads_and_verifies(self):
        dest = self.tmp / "a.pdf"
        self.assertTrue(download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp))
        self.assertEqual(dest.read_bytes(), PAYLOAD)

    def test_second_call_transfers_nothing(self):
        dest = self.tmp / "a.pdf"
        download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertFalse(download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp))

    def test_hash_mismatch_raises_and_leaves_no_file(self):
        _Handler.corrupt = True
        dest = self.tmp / "a.pdf"
        with self.assertRaises(ValueError) as cm:
            download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertIn("sha256", str(cm.exception).lower())
        self.assertFalse(dest.exists())

    def test_no_temp_files_are_left_behind_after_failure(self):
        _Handler.corrupt = True
        dest = self.tmp / "a.pdf"
        with self.assertRaises(ValueError):
            download_object(self.base + "objects/" + SHA, SHA, dest, self.tmp)
        self.assertEqual(list(self.tmp.glob("*.part")), [])


class TestFetchSubsetRefusesUnlistedPaths(ServerCase):
    def test_a_path_absent_from_the_manifest_is_refused(self):
        rows = [{"source_path": "manuals/ok/a.pdf", "sha256": SHA,
                 "file_size_bytes": len(PAYLOAD), "structural_subdir": False}]
        m = build_manifest(rows, self.base, "2026-01-01T00:00:00Z")
        m["files"][0]["source_path"] = "../escape.pdf"   # tamper after generation
        with self.assertRaises(CorpusWriteError):
            fetch_subset(m, "all", dest_root=ROOT, workers=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_fetch -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fence_evidence.fetch'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/fence_evidence/fetch.py
"""Fetch corpus objects from public object storage.

Anonymous: no credentials, no SDK. Every object is verified against the sha256
that is also its storage key, so a corrupted or substituted object cannot land
on disk.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .distribution import files_for_subset
from .paths import fetch_target

CHUNK = 1 << 20


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download_object(url: str, expected_sha256: str, dest: Path, tmp_dir: Path) -> bool:
    """Download url to dest, verifying sha256. Returns False if already present."""
    if dest.is_file() and _sha256_file(dest) == expected_sha256:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(url, timeout=60) as resp:
            for block in iter(lambda: resp.read(CHUNK), b""):
                h.update(block)
                out.write(block)
        got = h.hexdigest()
        if got != expected_sha256:
            raise ValueError(
                f"sha256 mismatch for {url}: expected {expected_sha256}, got {got}")
        shutil.move(str(tmp), str(dest))
        return True
    finally:
        if tmp.exists():
            tmp.unlink()


def fetch_subset(manifest: dict, subset: str, dest_root: Path,
                 workers: int = 4) -> dict:
    wanted = files_for_subset(manifest, subset)
    allowed = {f["source_path"] for f in manifest["files"]}
    base = manifest["base_url"]
    tmp_dir = Path(dest_root) / "workspace" / "tmp-fetch"

    # resolve every target before transferring anything: a manifest naming a
    # path outside the corpus must fail before the first byte is written
    targets = [(f, fetch_target(Path(dest_root) / f["source_path"], allowed))
               for f in wanted]

    result = {"requested": len(targets), "downloaded": 0, "already_present": 0,
              "bytes": 0, "failed": []}

    def one(item):
        f, dest = item
        try:
            got = download_object(base + f["key"], f["sha256"], dest, tmp_dir)
            return f, dest, got, None
        except Exception as e:  # noqa: BLE001 - reported per object, not raised
            return f, dest, False, f"{e.__class__.__name__}: {e}"

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for f, _dest, got, err in pool.map(one, targets):
            if err:
                result["failed"].append({"source_path": f["source_path"], "error": err})
            elif got:
                result["downloaded"] += 1
                result["bytes"] += f["bytes"]
            else:
                result["already_present"] += 1
    if tmp_dir.is_dir() and not any(tmp_dir.iterdir()):
        tmp_dir.rmdir()
    return result
```

- [ ] **Step 4: Register the CLI subcommand**

In `cli.py`, beside the other `add_parser` calls:

```python
    p = sub.add_parser("fetch", help="download corpus objects from public storage")
    p.add_argument("--subset", default="all",
                   help="all, structural, bufftech, china")
    p.add_argument("--manifest-url", default=None,
                   help="override the distribution manifest URL")
    p.add_argument("--workers", type=int, default=4)
```

and in the dispatch chain:

```python
    elif args.cmd == "fetch":
        from .fetch import fetch_subset, load_remote_manifest
        from .paths import REPO_ROOT
        manifest = load_remote_manifest(args.manifest_url)
        _print(fetch_subset(manifest, args.subset, REPO_ROOT, workers=args.workers))
```

Add to `fetch.py`:

```python
import json

DEFAULT_MANIFEST_URL_ENV = "FENCE_RAG_MANIFEST_URL"


def load_remote_manifest(url: str | None = None) -> dict:
    """Load the distribution manifest from a URL, or from the local workspace."""
    if url is None:
        url = os.environ.get(DEFAULT_MANIFEST_URL_ENV)
    if url is None:
        from .paths import CATALOG_DIR
        local = CATALOG_DIR / "distribution-manifest.json"
        if not local.is_file():
            raise FileNotFoundError(
                "no manifest URL given and workspace/catalog/distribution-manifest.json "
                "is absent; pass --manifest-url or run `cli publish --manifest`")
        return json.loads(local.read_text(encoding="utf-8"))
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

- [ ] **Step 5: Run tests**

Run: `cd tests && python3 -m unittest test_fetch -v && cd .. && python3 tests/run_tests.py`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/fence_evidence/fetch.py src/fence_evidence/cli.py tests/test_fetch.py
git commit -m "feat(dist): cli fetch with hash verification and idempotency"
```

---

### Task 6: `cli publish` — upload to R2

**Files:**
- Create: `src/fence_evidence/publish.py`
- Modify: `src/fence_evidence/cli.py`

**Interfaces:**
- Consumes: `R2Config` (Task 1), `sign_request` (Task 2), `build_manifest`/`load_corpus_manifest`/`object_key` (Task 3).
- Produces: `publish_objects(cfg: R2Config, rows: list[dict], dry_run: bool = True) -> dict`; `publish_manifest(cfg: R2Config, manifest: dict, dry_run: bool = True) -> dict`; `head_object(cfg, key) -> bool`.

- [ ] **Step 1: Write the implementation**

There is no unit test for the network path — it is credential-gated and cannot run in CI. Correctness comes from Task 2's signing tests plus the `--dry-run` default and the round-trip check in Step 3.

```python
# src/fence_evidence/publish.py
"""Publish corpus objects to Cloudflare R2. Maintainer-only.

Requires credentials in .env. Consuming the published corpus needs none of
this -- see fetch.py. Defaults to a dry run: nothing uploads unless --apply.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

from .config import R2Config
from .distribution import object_key
from .paths import REPO_ROOT
from .sigv4 import sign_request

CONTENT_TYPES = {".pdf": "application/pdf", ".png": "image/png",
                 ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 ".json": "application/json"}


def _request(cfg: R2Config, method: str, key: str, payload: bytes,
             content_type: str) -> int:
    url = f"{cfg.endpoint}/{cfg.bucket}/{key}"
    headers = sign_request(method, url, {"content-type": content_type}, payload,
                           cfg.access_key_id, cfg.secret_access_key,
                           region="auto", service="s3")
    req = urllib.request.Request(url, data=payload or None, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        if method == "HEAD" and e.code == 404:
            return 404
        raise RuntimeError(f"{method} {key} failed: HTTP {e.code}") from None


def head_object(cfg: R2Config, key: str) -> bool:
    return _request(cfg, "HEAD", key, b"", "application/octet-stream") == 200


def publish_objects(cfg: R2Config, rows: list[dict], dry_run: bool = True) -> dict:
    seen: set[str] = set()
    out = {"unique_objects": 0, "uploaded": 0, "already_present": 0,
           "skipped_duplicate_paths": 0, "bytes": 0, "dry_run": dry_run}
    for r in rows:
        sha = r["sha256"]
        if sha in seen:
            out["skipped_duplicate_paths"] += 1
            continue
        seen.add(sha)
        out["unique_objects"] += 1
        key = object_key(sha)
        if not dry_run and head_object(cfg, key):
            out["already_present"] += 1
            continue
        path = REPO_ROOT / r["source_path"]
        payload = path.read_bytes()
        got = hashlib.sha256(payload).hexdigest()
        if got != sha:
            raise RuntimeError(
                f"{r['source_path']} does not match its manifest sha256 "
                f"(expected {sha}, got {got}); re-run `cli manifest`")
        out["bytes"] += len(payload)
        if dry_run:
            continue
        _request(cfg, "PUT", key, payload,
                 CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"))
        out["uploaded"] += 1
    return out


def publish_manifest(cfg: R2Config, manifest: dict, dry_run: bool = True) -> dict:
    payload = json.dumps(manifest, indent=1, sort_keys=True).encode("utf-8")
    local = REPO_ROOT / "workspace" / "catalog" / "distribution-manifest.json"
    from .paths import open_write
    with open_write(local) as fh:
        fh.write(payload.decode("utf-8"))
    if not dry_run:
        _request(cfg, "PUT", "distribution-manifest.json", payload, "application/json")
    return {"bytes": len(payload), "local": str(local.relative_to(REPO_ROOT)),
            "dry_run": dry_run}
```

- [ ] **Step 2: Register the CLI subcommand**

```python
    p = sub.add_parser("publish", help="upload the corpus to public object storage (maintainer)")
    p.add_argument("--apply", action="store_true", help="actually upload; default is a dry run")
    p.add_argument("--manifest-only", action="store_true")
```

```python
    elif args.cmd == "publish":
        from .config import load_env, R2Config
        from .distribution import build_manifest, load_corpus_manifest
        from .publish import publish_objects, publish_manifest
        from datetime import datetime, timezone
        cfg = R2Config.from_env(load_env())
        rows = load_corpus_manifest()
        manifest = build_manifest(
            rows, cfg.public_base_url,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        out = {"config": cfg.redacted(),
               "manifest": publish_manifest(cfg, manifest, dry_run=not args.apply)}
        if not args.manifest_only:
            out["objects"] = publish_objects(cfg, rows, dry_run=not args.apply)
        _print(out)
```

- [ ] **Step 3: Verify the dry run reports 128 unique objects and no secret**

Run: `python3 -m fence_evidence.cli publish 2>&1 | head -30`
Expected: `"unique_objects": 128`, `"skipped_duplicate_paths": 16`, `"dry_run": true`, `"secret_access_key": "<redacted>"`. Confirm no credential appears anywhere in the output.

- [ ] **Step 4: Upload for real, then round-trip**

```bash
python3 -m fence_evidence.cli publish --apply
python3 -m fence_evidence.cli fetch --subset china --manifest-url "<R2_PUBLIC_BASE_URL>distribution-manifest.json"
```
Expected: the second command reports `already_present: 4` on a full checkout — proving the published bytes hash-match what is on disk.

- [ ] **Step 5: Commit**

```bash
git add src/fence_evidence/publish.py src/fence_evidence/cli.py
git commit -m "feat(dist): cli publish uploads content-addressed objects to R2"
```

---

### Task 7: `resolve_asset` — derived images become a cache

**Files:**
- Modify: `src/fence_evidence/paths.py`, `retrieval.py:401,485`, `noa_tables.py:120`, `facts.py:226`, `evaluate.py:213`
- Test: `tests/test_asset_cache.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `resolve_asset(rel_path: str | None) -> Path | None` — returns a local path for a derived asset, rendering it from the source PDF if absent, or `None` when it cannot be produced.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_asset_cache.py
"""resolve_asset materialises derived images on demand."""
import unittest
from pathlib import Path

from context import ROOT, requires_store  # noqa: F401
from fence_evidence.paths import resolve_asset, REPO_ROOT


class TestResolveAsset(unittest.TestCase):
    def test_none_input_returns_none(self):
        self.assertIsNone(resolve_asset(None))

    def test_existing_file_is_returned_unchanged(self):
        existing = "workspace/catalog/corpus-manifest.jsonl"
        if not (REPO_ROOT / existing).is_file():
            self.skipTest("manifest not built")
        self.assertEqual(resolve_asset(existing), (REPO_ROOT / existing).resolve())

    def test_unresolvable_asset_returns_none_rather_than_raising(self):
        self.assertIsNone(resolve_asset("workspace/derived/doc-nope/pages/9999.png"))

    @requires_store
    def test_rerender_reproduces_the_stored_page_image_bytes(self):
        """D5: an on-demand render matches what ingest wrote."""
        import sqlite3, hashlib, shutil, tempfile
        from fence_evidence.paths import EVIDENCE_DB
        conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT page_image_path FROM pages WHERE page_image_path IS NOT NULL LIMIT 20"
        ).fetchall()
        conn.close()
        checked = 0
        for (rel,) in rows:
            src = REPO_ROOT / rel
            if not src.is_file():
                continue
            original = hashlib.sha256(src.read_bytes()).hexdigest()
            backup = Path(tempfile.mkdtemp()) / "orig.png"
            shutil.copy2(src, backup)
            try:
                src.unlink()
                produced = resolve_asset(rel)
                if produced is None:
                    self.skipTest("source PDF absent; cannot re-render")
                self.assertEqual(hashlib.sha256(produced.read_bytes()).hexdigest(), original)
                checked += 1
            finally:
                shutil.copy2(backup, src)
            if checked >= 3:
                break
        if checked == 0:
            self.skipTest("no page images available to re-render")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tests && python3 -m unittest test_asset_cache -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_asset'`

- [ ] **Step 3: Write minimal implementation**

Add to `paths.py`:

```python
def resolve_asset(rel_path: "str | None") -> "Path | None":
    """Return a local path for a derived asset, materialising it if absent.

    workspace/derived/ is a cache, not a data source: every page image is a
    deterministic render of a source PDF page. Resolution order is
    cache hit -> render from the PDF -> None. None is a legitimate result and
    callers must handle it; the DOCX has no page image at all.
    """
    if not rel_path:
        return None
    target = (REPO_ROOT / rel_path).resolve()
    if target.is_file():
        return target
    from .assets import render_page_image   # local import keeps paths.py dependency-free
    try:
        return render_page_image(rel_path)
    except Exception:
        return None
```

Create `src/fence_evidence/assets.py`:

```python
"""Re-render a derived page image from its source PDF."""
from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from .paths import EVIDENCE_DB, REPO_ROOT, ensure_writable


def render_page_image(rel_path: str) -> Path | None:
    """Render the page image identified by rel_path, or return None."""
    if not EVIDENCE_DB.is_file():
        return None
    conn = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    try:
        row = conn.execute(
            """SELECT p.page_no, p.page_image_dpi, d.source_path
                 FROM pages p
                 JOIN document_versions v ON p.version_id = v.version_id
                 JOIN documents d ON v.document_id = d.document_id
                WHERE p.page_image_path = ?""", (rel_path,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    page_no, dpi, source_path = row
    pdf = REPO_ROOT / source_path
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        return None
    out = ensure_writable(REPO_ROOT / rel_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.with_suffix("")
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi or 200),
         "-f", str(page_no), "-l", str(page_no), "-singlefile", str(pdf), str(stem)],
        check=True, capture_output=True)
    return out if out.is_file() else None
```

- [ ] **Step 4: Route the five call sites through it**

Replace each `REPO_ROOT / <rel>` for a derived image with `resolve_asset(<rel>)`, and handle `None`:

- `retrieval.py:401` and `:485`
- `noa_tables.py:120`
- `facts.py:226`
- `evaluate.py:213` — already tolerates a missing image; keep that behaviour.

- [ ] **Step 5: Run the whole suite**

Run: `python3 tests/run_tests.py`
Expected: OK. `tests/test_contract.py` asserts page images resolve for search results — it must still pass.

- [ ] **Step 6: Commit**

```bash
git add src/fence_evidence/paths.py src/fence_evidence/assets.py src/fence_evidence/retrieval.py \
        src/fence_evidence/noa_tables.py src/fence_evidence/facts.py src/fence_evidence/evaluate.py \
        tests/test_asset_cache.py
git commit -m "feat(dist): resolve derived images on demand, making derived/ a cache"
```

---

### Task 8: Prove `derived/` is a cache (acceptance criterion D6)

**Files:**
- Modify: `docs/distribution-design.md` (record the measured result)

- [ ] **Step 1: Record the baseline**

```bash
python3 -m fence_evidence.cli evaluate > /tmp/eval-before.json
```

- [ ] **Step 2: Move `derived/` aside — do not delete it**

```bash
mv workspace/derived workspace/derived.parked
```

- [ ] **Step 3: Re-run the evaluation**

```bash
python3 -m fence_evidence.cli evaluate > /tmp/eval-after.json
diff <(python3 -m json.tool /tmp/eval-before.json) <(python3 -m json.tool /tmp/eval-after.json)
```
Expected: no differences in `doc_recall_at_10`, `evidence_support`, `page_support`, `no_answer_precision`, `false_unsupported_rate`. Any difference means `derived/` is a data source and the design's §6 claim is wrong — stop and report rather than proceeding.

- [ ] **Step 4: Restore**

```bash
rm -rf workspace/derived && mv workspace/derived.parked workspace/derived
```

- [ ] **Step 5: Record the result in the design doc**

Add the measured outcome under §9 D6, with the date and the exact metric values compared.

- [ ] **Step 6: Commit**

```bash
git add docs/distribution-design.md
git commit -m "docs(dist): record the D6 measurement proving derived/ is a cache"
```

---

## Self-Review

**Spec coverage.** §2 what-is-stored → Task 3 + 6. §3 bucket layout and content-addressed keys → Task 3 (`object_key`) + Task 6. §4 fetch manifest → Task 3. §5 client → Task 5, with the write guard split into Task 4 because it is the security boundary and deserves its own gate. §6 page images on demand → Task 7. §7 migration (LFS untouched) → no code; `.gitattributes` is not modified by any task, which is the requirement. §8 non-goals → nothing to build. §9 acceptance: D1 `bootstrap.sh` (already shipped), D2 Task 6 step 4, D3 Task 5 tests, D4 Task 5 `test_second_call_transfers_nothing`, D5 Task 7 `test_rerender_reproduces_the_stored_page_image_bytes`, D6 Task 8, D7 Task 4.

**Placeholders.** None. Every code step carries runnable code; no "add error handling" or "similar to Task N".

**Type consistency.** `object_key(sha256) -> str` used identically in Tasks 3, 5, 6. `R2Config.public_base_url` always slash-terminated (Task 1) so `base + f["key"]` in Task 5 concatenates correctly. `fetch_target(path, allowed: set[str])` matches its Task 5 call site. `resolve_asset` returns `Path | None` in both Task 7 definition and call sites.

**Known gap, deliberately left:** Task 6 has no automated network test — it is credential-gated and cannot run in CI. It is covered by Task 2's signing vectors, the `--dry-run` default, and the Task 6 step 4 round-trip.
