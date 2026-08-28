"""Transport tests: `dispatch()` without a socket, `serve()` with exactly one.

D5 of the Phase 2 design says the transport holds no logic and is tested
independently of it, so every test here fakes the service layer
(`sourcerefs`, `reviews`, `cropcache`) rather than importing it. That is not a
workaround for those modules being written in parallel -- it is the property
being asserted: `api.py` must be able to answer 401, 404, 405 and 413 with no
store, no crop and no review code reachable at all.

Covers acceptance 6 (dispatch without a socket, one smoke test for serve),
7 (batch cap and the deadline), 8 (401 before any store access) and
9 (every code is `error.*` and none is a warning-registry code).
"""
import json
import threading
import types
import unittest
import urllib.error
import urllib.request

import context  # noqa: F401  -- puts the repo root on sys.path
import fence_evidence
from fence_evidence import api

TOKEN = "planning-backend-token"
TOKENS = {TOKEN, "second-issued-token"}


class _ExplodingConn:
    """A connection that fails the test if anything touches it.

    Acceptance 8 is "401 before any *store access*", which is stronger than
    "401 before a query" -- this catches a handler that reaches for the store
    to decide something before checking the token.
    """

    def __getattr__(self, name):
        raise AssertionError(f"the store was touched: conn.{name}")


class _FakeService(unittest.TestCase):
    """Installs fake service modules as attributes of the package.

    `dispatch` does `from . import sourcerefs` inside the handler, which
    resolves by attribute lookup on the already-imported package before the
    import system is asked for a file -- so setting the attribute is enough,
    and nothing on disk is needed or shadowed beyond the test.
    """

    def setUp(self):
        self.calls = []

        class ReviewRefused(RuntimeError):
            def __init__(self, code, message=""):
                super().__init__(message or code)
                self.code = code

        self.ReviewRefused = ReviewRefused
        self.sourcerefs = types.SimpleNamespace(
            source_ref=self._source_ref, source_refs_batch=self._batch)
        self.reviews = types.SimpleNamespace(
            ReviewRefused=ReviewRefused, submit_review=self._submit)

        # What the fakes return or raise; a test overrides before dispatching.
        self.ref_result = {"id": "ab" * 8, "page_no": 47, "text": "Call before you dig."}
        self.ref_raises = None
        self.batch_result = {"refs": [], "not_rendered": [], "deadline_exceeded": False}
        self.batch_raises = None
        self.review_result = {"review_id": "r0", "verdict": "accepted",
                              "cells_written": 18, "promotable": 18}
        self.review_raises = None

        self._saved = {}
        for name in ("sourcerefs", "reviews"):
            self._saved[name] = getattr(fence_evidence, name, None)
            setattr(fence_evidence, name, getattr(self, name))
        self.addCleanup(self._restore)

    def _restore(self):
        for name, original in self._saved.items():
            if original is None:
                delattr(fence_evidence, name)
            else:
                setattr(fence_evidence, name, original)

    def _source_ref(self, conn, ref_id, **kw):
        self.calls.append(("source_ref", ref_id))
        if self.ref_raises is not None:
            raise self.ref_raises
        return self.ref_result

    def _batch(self, conn, ref_ids, **kw):
        self.calls.append(("batch", tuple(ref_ids)))
        if self.batch_raises is not None:
            raise self.batch_raises
        return self.batch_result

    def _submit(self, conn, **kw):
        self.calls.append(("submit_review", kw))
        if self.review_raises is not None:
            raise self.review_raises
        return self.review_result

    def go(self, method, path, body=None, *, token=TOKEN, conn="conn"):
        return api.dispatch(method, path, body, conn=conn, token=token, tokens=TOKENS)


def code_of(payload):
    return payload["error"]["code"]


class TestAuth(_FakeService):
    """Spec §5.2 401, and acceptance 8: before any store access."""

    def test_a_missing_token_is_401_and_never_reaches_the_store(self):
        status, payload = self.go("GET", "/source-refs/abc", token=None,
                                  conn=_ExplodingConn())
        self.assertEqual(status, 401)
        self.assertEqual(code_of(payload), "error.unauthorized")
        self.assertEqual(self.calls, [])

    def test_an_unknown_token_is_401(self):
        status, payload = self.go("POST", "/reviews", {}, token="not-issued",
                                  conn=_ExplodingConn())
        self.assertEqual(status, 401)
        self.assertEqual(code_of(payload), "error.unauthorized")

    def test_an_empty_allowlist_authorizes_nobody(self):
        status, _ = api.dispatch("GET", "/source-refs/abc", None,
                                 conn=_ExplodingConn(), token=TOKEN, tokens=set())
        self.assertEqual(status, 401)

    def test_an_empty_string_token_is_401_not_a_match(self):
        status, _ = api.dispatch("GET", "/source-refs/abc", None,
                                 conn=_ExplodingConn(), token="", tokens={""})
        self.assertEqual(status, 401)

    def test_a_non_ascii_token_is_401_rather_than_a_TypeError(self):
        """`hmac.compare_digest` raises on non-ASCII str; that must not be a 500."""
        status, _ = self.go("GET", "/source-refs/abc", token="tokén",
                            conn=_ExplodingConn())
        self.assertEqual(status, 401)

    def test_either_issued_token_is_accepted(self):
        for token in sorted(TOKENS):
            with self.subTest(token=token):
                status, _ = self.go("GET", "/source-refs/abc", token=token)
                self.assertEqual(status, 200)

    def test_auth_precedes_routing_so_paths_do_not_leak(self):
        status, payload = self.go("GET", "/snapshots/xyz", token=None,
                                  conn=_ExplodingConn())
        self.assertEqual(status, 401)
        self.assertEqual(code_of(payload), "error.unauthorized")


class TestRouting(_FakeService):
    """Three routes and nothing else; spec §8 keeps the other five calls out."""

    def test_an_unrouted_path_is_404(self):
        for path in ("/", "/search", "/claims", "/part-types", "/documents",
                     "/gaps", "/source-refs", "/source-refs/", "/reviews/9"):
            with self.subTest(path=path):
                status, payload = self.go("GET", path)
                self.assertEqual(status, 404)
                self.assertEqual(code_of(payload), "error.not_found")

    def test_a_wrong_method_on_a_known_path_is_405(self):
        for method, path in (("GET", "/reviews"), ("DELETE", "/reviews"),
                             ("GET", "/source-refs:batch"),
                             ("POST", "/source-refs/abc"),
                             ("PUT", "/source-refs/abc")):
            with self.subTest(method=method, path=path):
                status, payload = self.go(method, path, {})
                self.assertEqual(status, 405)
                self.assertEqual(code_of(payload), "error.method_not_allowed")
        self.assertEqual(self.calls, [], "a rejected verb reached the service layer")

    def test_a_query_string_does_not_defeat_the_route(self):
        status, _ = self.go("GET", "/source-refs/abc?dpi=200")
        self.assertEqual(status, 200)
        self.assertEqual(self.calls, [("source_ref", "abc")])

    def test_a_trailing_slash_is_tolerated(self):
        self.assertEqual(self.go("POST", "/reviews/", {})[0], 200)
        self.assertEqual(self.go("GET", "/source-refs/abc/")[0], 200)

    def test_a_percent_encoded_id_is_decoded_once(self):
        self.go("GET", "/source-refs/ab%2Dcd")
        self.assertEqual(self.calls, [("source_ref", "ab-cd")])

    def test_the_batch_path_is_not_the_id_path(self):
        """`/source-refs:batch` shares a prefix with the id route but is a POST."""
        status, _ = self.go("POST", "/source-refs:batch", {"ids": ["a"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.calls, [("batch", ("a",))])


class TestSourceRef(_FakeService):
    """`GET /source-refs/{id}`; spec §5.1."""

    def test_the_service_dict_is_returned_verbatim(self):
        status, payload = self.go("GET", "/source-refs/eb2c863494b90243")
        self.assertEqual(status, 200)
        self.assertIs(payload, self.ref_result)

    def test_an_unknown_ref_is_404_unknown_ref(self):
        self.ref_raises = KeyError("eb2c")
        status, payload = self.go("GET", "/source-refs/eb2c")
        self.assertEqual(status, 404)
        self.assertEqual(code_of(payload), "error.unknown_ref")

    def test_a_lookup_error_of_any_kind_is_404(self):
        self.ref_raises = LookupError("gone")
        self.assertEqual(self.go("GET", "/source-refs/eb2c")[0], 404)

    def test_a_None_result_is_404_rather_than_a_null_body(self):
        """`refs.resolve` returns None for an unknown id; a wrapper may pass it on."""
        self.ref_result = None
        status, payload = self.go("GET", "/source-refs/eb2c")
        self.assertEqual(status, 404)
        self.assertEqual(code_of(payload), "error.unknown_ref")

    def test_an_uncroppable_ref_is_404(self):
        """`crops.CropError` means we have nothing to show; §5.1 has no other 404."""
        from fence_evidence.crops import CropError
        self.ref_raises = CropError("no page image")
        self.assertEqual(self.go("GET", "/source-refs/eb2c")[0], 404)

    def test_an_unexpected_failure_is_not_swallowed(self):
        """Transport maps the errors it was given a code for and no others."""
        self.ref_raises = RuntimeError("disk on fire")
        with self.assertRaises(RuntimeError):
            self.go("GET", "/source-refs/eb2c")


class TestBatch(_FakeService):
    """`POST /source-refs:batch`; acceptance 7."""

    def test_a_batch_at_the_cap_is_accepted(self):
        ids = [f"{i:016x}" for i in range(api.BATCH_CAP)]
        status, _ = self.go("POST", "/source-refs:batch", {"ids": ids})
        self.assertEqual(status, 200)

    def test_a_batch_over_the_cap_is_413_and_costs_nothing(self):
        ids = [f"{i:016x}" for i in range(api.BATCH_CAP + 1)]
        status, payload = self.go("POST", "/source-refs:batch", {"ids": ids},
                                  conn=_ExplodingConn())
        self.assertEqual(status, 413)
        self.assertEqual(code_of(payload), "error.batch_too_large")
        self.assertEqual(self.calls, [], "an oversized batch reached the service")

    def test_the_cap_is_fifty(self):
        self.assertEqual(api.BATCH_CAP, 50)

    def test_a_service_side_ValueError_is_also_413(self):
        self.batch_raises = ValueError("cap is 25 here")
        status, payload = self.go("POST", "/source-refs:batch", {"ids": ["a"]})
        self.assertEqual(status, 413)
        self.assertEqual(code_of(payload), "error.batch_too_large")

    def test_a_deadline_returns_partial_results_and_never_an_error(self):
        self.batch_result = {"refs": [{"id": "a"}], "not_rendered": ["b"],
                             "deadline_exceeded": True}
        status, payload = self.go("POST", "/source-refs:batch", {"ids": ["a", "b"]})
        self.assertEqual(status, 200)
        self.assertTrue(payload["deadline_exceeded"])
        self.assertEqual(payload["not_rendered"], ["b"])

    def test_an_unrendered_id_is_not_a_404(self):
        """Unknown ids come back in `not_rendered`; a whole batch never 404s."""
        self.batch_result = {"refs": [], "not_rendered": ["a"], "deadline_exceeded": False}
        self.assertEqual(self.go("POST", "/source-refs:batch", {"ids": ["a"]})[0], 200)

    def test_an_empty_batch_is_legal(self):
        self.assertEqual(self.go("POST", "/source-refs:batch", {"ids": []})[0], 200)

    def test_a_malformed_body_is_refused_before_the_service(self):
        for body in (None, [], {"ids": "abc"}, {"ids": [1, 2]}, {}):
            with self.subTest(body=body):
                status, payload = self.go("POST", "/source-refs:batch", body,
                                          conn=_ExplodingConn())
                self.assertEqual(status, 422)
                self.assertEqual(code_of(payload), "error.malformed_request")
        self.assertEqual(self.calls, [])


class TestReviews(_FakeService):
    """`POST /reviews`; spec §5.2."""

    BODY = {"crop_sha256": "f" * 64, "reviewer": "j.doe", "verdict": "accepted",
            "grid": [{"row": 0, "col": 1, "value": '30"'}],
            "spans": [{"row_from": 0, "row_to": 1, "col": 3, "text": "NON HVHZ"}],
            "notes": None}

    def test_the_happy_path_returns_the_service_dict(self):
        status, payload = self.go("POST", "/reviews", dict(self.BODY))
        self.assertEqual(status, 200)
        self.assertEqual(payload["review_id"], "r0")
        self.assertEqual(payload["promotable"], 18)

    def test_the_body_is_passed_through_as_keywords(self):
        self.go("POST", "/reviews", dict(self.BODY))
        (_, kw), = self.calls
        self.assertEqual(kw["crop_sha256"], "f" * 64)
        self.assertEqual(kw["reviewer"], "j.doe")
        self.assertEqual(kw["verdict"], "accepted")
        self.assertEqual(kw["grid"], self.BODY["grid"])
        self.assertEqual(kw["spans"], self.BODY["spans"])

    def test_absent_spans_become_the_empty_list_not_None(self):
        body = dict(self.BODY)
        del body["spans"]
        self.go("POST", "/reviews", body)
        (_, kw), = self.calls
        self.assertEqual(kw["spans"], [])

    def test_reviewed_at_is_ours_and_is_not_taken_from_the_request(self):
        """It is half of `review_id`; a client choosing it chooses what it overwrites."""
        self.go("POST", "/reviews", dict(self.BODY, reviewed_at="1999-01-01T00:00:00Z"))
        (_, kw), = self.calls
        self.assertNotIn("reviewed_at", kw)

    def test_a_crop_mismatch_is_409(self):
        self.review_raises = self.ReviewRefused("error.crop_mismatch", "echo differs")
        status, payload = self.go("POST", "/reviews", dict(self.BODY))
        self.assertEqual(status, 409)
        self.assertEqual(code_of(payload), "error.crop_mismatch")

    def test_a_malformed_review_is_422(self):
        self.review_raises = self.ReviewRefused("error.malformed_review",
                                                "span outside the grid")
        status, payload = self.go("POST", "/reviews", dict(self.BODY))
        self.assertEqual(status, 422)
        self.assertEqual(code_of(payload), "error.malformed_review")

    def test_a_bare_code_is_normalised_into_the_error_namespace(self):
        """Transport owns the namespace rule; a service typo must not escape it."""
        self.review_raises = self.ReviewRefused("crop_mismatch")
        status, payload = self.go("POST", "/reviews", dict(self.BODY))
        self.assertEqual(status, 409)
        self.assertEqual(code_of(payload), "error.crop_mismatch")

    def test_an_unrecognised_refusal_code_still_refuses(self):
        self.review_raises = self.ReviewRefused("error.something_new")
        status, payload = self.go("POST", "/reviews", dict(self.BODY))
        self.assertEqual(status, 422)
        self.assertEqual(code_of(payload), "error.malformed_review")

    def test_a_refusal_without_a_code_is_not_a_200(self):
        self.review_raises = self.ReviewRefused(None, "no code set")
        self.assertEqual(self.go("POST", "/reviews", dict(self.BODY))[0], 422)

    def test_a_non_object_body_is_422_before_the_service(self):
        for body in (None, [], "accepted", 5):
            with self.subTest(body=body):
                status, payload = self.go("POST", "/reviews", body,
                                          conn=_ExplodingConn())
                self.assertEqual(status, 422)
                self.assertEqual(code_of(payload), "error.malformed_request")

    def test_field_validation_is_not_transport_business(self):
        """D5: a bad verdict is `reviews.py`'s refusal, not a shape check here."""
        self.go("POST", "/reviews", {"verdict": "maybe"})
        (_, kw), = self.calls
        self.assertEqual(kw["verdict"], "maybe")


class TestErrorNamespace(_FakeService):
    """Acceptance 9. Planning's `test_locale_bundles.py` is the thing at risk."""

    def _every_code_dispatch_can_emit(self):
        seen = set()

        def record(result):
            status, payload = result
            if "error" in payload:
                seen.add(payload["error"]["code"])

        record(self.go("GET", "/source-refs/a", token=None, conn=_ExplodingConn()))
        record(self.go("GET", "/nope"))
        record(self.go("GET", "/reviews"))
        record(self.go("POST", "/source-refs:batch",
                       {"ids": ["x"] * (api.BATCH_CAP + 1)}))
        record(self.go("POST", "/reviews", None))
        self.ref_raises = KeyError("x")
        record(self.go("GET", "/source-refs/a"))
        self.ref_raises = None
        self.review_raises = self.ReviewRefused("error.crop_mismatch")
        record(self.go("POST", "/reviews", {}))
        return seen

    def test_every_emitted_code_is_in_the_error_namespace(self):
        for code in self._every_code_dispatch_can_emit():
            with self.subTest(code=code):
                self.assertTrue(code.startswith("error."),
                                f"{code} is outside the error.* namespace")

    def test_every_declared_code_is_in_the_error_namespace(self):
        for code in api.ERROR_CODES:
            self.assertTrue(code.startswith("error."), code)

    def test_no_code_could_be_mistaken_for_a_warning_registry_code(self):
        """Registry codes are UPPER_SNAKE (`SOURCE_TEXT_FROM_OCR`). Ours never are."""
        for code in api.ERROR_CODES:
            with self.subTest(code=code):
                self.assertEqual(code, code.lower())
                self.assertNotIn(" ", code)

    def test_every_reachable_branch_was_actually_exercised(self):
        """Guards the test above from passing because it emitted nothing."""
        self.assertGreaterEqual(len(self._every_code_dispatch_can_emit()), 6)

    def test_the_five_wire_codes_carry_the_statuses_the_spec_fixed(self):
        self.assertEqual(
            {c: api._STATUS[c] for c in
             ("error.unauthorized", "error.unknown_ref", "error.crop_mismatch",
              "error.batch_too_large", "error.malformed_review")},
            {"error.unauthorized": 401, "error.unknown_ref": 404,
             "error.crop_mismatch": 409, "error.batch_too_large": 413,
             "error.malformed_review": 422})

    def test_an_error_body_has_the_shape_planning_parses(self):
        _, payload = self.go("GET", "/nope")
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(set(payload["error"]), {"code", "message"})
        self.assertIsInstance(payload["error"]["message"], str)


class TestServeSmoke(_FakeService):
    """Acceptance 6: one socket in the whole suite, and no store behind it.

    `_open_conn` is replaced because a real connection would create
    `workspace/indexes/evidence.db`; the fakes never look at it.
    """

    def setUp(self):
        super().setUp()
        self.opened = 0

        def fake_open():
            self.opened += 1
            return None

        original = api._open_conn
        api._open_conn = fake_open
        self.addCleanup(setattr, api, "_open_conn", original)

        self.server = api.make_server("127.0.0.1", 0, tokens=TOKENS)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _request(self, method, path, body=None, token=TOKEN):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method)
        if token is not None:
            req.add_header("Authorization", f"Bearer {token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read()), resp.headers
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read()), exc.headers

    def test_a_real_request_reaches_dispatch_and_comes_back_as_json(self):
        status, payload, headers = self._request("GET", "/source-refs/eb2c")
        self.assertEqual(status, 200)
        self.assertEqual(payload, self.ref_result)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(self.calls, [("source_ref", "eb2c")])

    def test_a_posted_body_is_parsed_and_handed_to_the_service(self):
        status, payload, _ = self._request("POST", "/reviews",
                                           {"verdict": "accepted", "grid": []})
        self.assertEqual(status, 200)
        self.assertEqual(payload["review_id"], "r0")

    def test_an_unauthorized_request_is_401_and_opens_no_store(self):
        status, payload, _ = self._request("GET", "/source-refs/eb2c", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(code_of(payload), "error.unauthorized")
        self.assertEqual(self.opened, 0, "a 401 paid for a database connection")


if __name__ == "__main__":
    unittest.main()
