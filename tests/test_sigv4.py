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
        self.assertEqual(cr.splitlines()[1], "/bucket/a%2520b/c")


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
