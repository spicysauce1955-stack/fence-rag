"""HTTP transport for the three calls Planning makes into this platform.

Routing, auth and error mapping. **No logic.** D5 of
`docs/superpowers/specs/2026-08-27-phase-2-review-loop-design.md`: every
endpoint's behaviour lives in a module that takes arguments and returns dicts,
so this file can be tested without a socket and those modules can be tested
without a request. `dispatch()` is pure -- no sockets, no printing, no global
state -- and is what the suite drives; `serve()` is the thin shell around it.

Three things about the shape of this file are consequences of measurements or
constraints recorded elsewhere, not preferences:

1. **The service modules are imported inside the handlers, never at module
   import time.** Partly so a transport test never needs `reviews.py`,
   `sourcerefs.py` or `cropcache.py` to exist, and partly because importing
   them drags in poppler-shelling code that a 401 must not pay for.

2. **One bearer token on an allowlist; no CORS, no sessions, no per-user rate
   limiting.** §4 of `2026-08-27-unblocking-planning-design.md`: every path is
   frontend -> Planning backend -> here. This service accepts connections from
   one backend and never from a browser, so the machinery that exists to make
   a browser safe would be answering a question nobody is asking.

3. **Every error code is in the `error.*` namespace and none may be a warning
   registry code.** Registry codes are `UPPER_SNAKE` and Planning's
   `test_locale_bundles.py` fails their build on any registry code lacking
   both locale bundles -- so an HTTP error code that leaked into that namespace
   would break their CI on our commit. `tests/test_api.py` asserts the
   namespace over every code this module can emit.
"""
from __future__ import annotations

import hmac
import json
from urllib.parse import unquote

# Spec §5.1 and §7. The cap is well below 100 because crop rendering is
# bimodal -- ~1.2 s for 50 at the median, ~6.7 s with one p99 render in the
# batch -- and the connection is occupied on Planning's side too.
BATCH_CAP = 50

# A request body larger than this is refused unread. A review of the largest
# table in the queue is a few kilobytes; nothing legitimate approaches this.
SOCKET_TIMEOUT_S = 30.0   # a silent client must not hold a thread
MAX_BODY_BYTES = 1 << 20

# The one mapping table. Spec §5.2 fixes the five middle rows; `not_found`,
# `method_not_allowed` and `internal` are transport-level and are *not* on the
# wire contract Planning builds against -- they are what an HTTP server has to
# say when there is no route, no verb, or a bug. They are named here rather
# than invented at each call site so the namespace test can enumerate them.
_STATUS: dict[str, int] = {
    "error.unauthorized": 401,       # §5.2: missing or unknown bearer token
    "error.not_found": 404,          # transport: no such route
    "error.unknown_ref": 404,        # §5.2: no such ref_id
    "error.method_not_allowed": 405,  # transport: known path, wrong verb
    "error.crop_mismatch": 409,      # §5.2: the echo is not what we would serve
    "error.batch_too_large": 413,    # §5.2: more than BATCH_CAP ids
    "error.request_too_large": 413,  # transport: body over MAX_BODY_BYTES
    "error.malformed_request": 422,  # transport: body is not the shape the route takes
    "error.malformed_review": 422,   # §5.2: bad verdict, bad grid, span outside grid
    "error.internal": 500,           # transport: emitted by serve(), never by dispatch()
}

ERROR_CODES = frozenset(_STATUS)


def _error(code: str, message: str) -> "tuple[int, dict]":
    return _STATUS[code], {"error": {"code": code, "message": message}}


def _authorized(token: str | None, tokens: "set[str]") -> bool:
    """Constant-time membership of the bearer allowlist.

    `hmac.compare_digest` rather than `==` so a token cannot be recovered a
    character at a time from response timing. Every entry is compared even
    after a match, so the position of a token in the allowlist does not leak
    either. A non-ASCII `str` makes `compare_digest` raise `TypeError`; that is
    a token we do not issue, so it is simply not authorized.
    """
    if not token or not tokens:
        return False
    found = False
    for allowed in tokens:
        try:
            if hmac.compare_digest(token, allowed):
                found = True
        except TypeError:
            continue
    return found


def _missing_types() -> tuple:
    """Exception classes that mean "we cannot show you this ref".

    Built at call time, not at import: `cropcache` may not be importable in a
    checkout that has not run it yet, and the transport must degrade to the
    stdlib lookup errors rather than fail to import.
    """
    types: list[type] = [LookupError]  # KeyError and IndexError are subclasses
    for name in ("cropcache", "crops"):
        try:
            module = __import__(f"{__package__}.{name}", fromlist=["*"])
        except ImportError:
            continue
        for attr in ("CropUnavailable", "CropError"):
            exc = getattr(module, attr, None)
            # `cropcache` re-exports `crops.CropError`, so dedupe by identity.
            if (isinstance(exc, type) and issubclass(exc, BaseException)
                    and exc not in types):
                types.append(exc)
    return tuple(types)


def _refused(exc: Exception) -> "tuple[int, dict]":
    """Map a `reviews.ReviewRefused` onto its HTTP status by its `.code`.

    Two tolerances, both deliberate. A bare `crop_mismatch` is normalised to
    `error.crop_mismatch`, because the namespace rule is this module's job to
    enforce and a service module that forgets the prefix should not be able to
    put a registry-shaped code on the wire. An unrecognised code becomes
    `error.malformed_review`, the generic "this review was not acceptable" of
    the table -- a refusal must never fall through to a 200.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, str):
        if not code.startswith("error."):
            code = f"error.{code}"
        if code in _STATUS:
            return _error(code, str(exc) or code)
    return _error("error.malformed_review", str(exc) or "review refused")


def _get_source_ref(ref_id: str, *, conn) -> "tuple[int, dict]":
    from . import sourcerefs  # lazy: see the module docstring

    try:
        ref = sourcerefs.source_ref(conn, ref_id)
    except _missing_types():
        ref = None
    if ref is None:
        return _error("error.unknown_ref", f"no such source ref: {ref_id}")
    return 200, ref


def _post_batch(body: dict | None, *, conn) -> "tuple[int, dict]":
    if not isinstance(body, dict):
        return _error("error.malformed_request", "request body must be a JSON object")
    ids = body.get("ids")
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        # The wire table has no generic malformed-request code and inventing one
        # would be a change Planning has not agreed to, so the malformed-body
        # code covers both bodies. Noted in the handover as a spec gap.
        return _error("error.malformed_request", "`ids` must be a list of strings")
    if len(ids) > BATCH_CAP:
        # Checked here so an oversized batch costs no store access and no
        # render, and so the refusal does not depend on the service module
        # having been written yet.
        return _error("error.batch_too_large",
                      f"{len(ids)} ids requested; the cap is {BATCH_CAP}")

    from . import sourcerefs  # lazy: see the module docstring

    try:
        result = sourcerefs.source_refs_batch(conn, ids, cap=BATCH_CAP)
    except ValueError as exc:
        # Reachable only if the service enforces a smaller cap than ours.
        return _error("error.batch_too_large", str(exc) or "batch too large")
    # An unknown id is *not* an error here: §5.1 says a batch reports them in
    # `not_rendered` and a deadline returns partial results with
    # `deadline_exceeded: true`, because a reviewer seeing nothing is worse.
    return 200, result


def _post_review(body: dict | None, *, conn) -> "tuple[int, dict]":
    if not isinstance(body, dict):
        return _error("error.malformed_request", "request body must be a JSON object")

    from . import reviews  # lazy: see the module docstring

    try:
        result = reviews.submit_review(
            conn,
            crop_sha256=body.get("crop_sha256"),
            reviewer=body.get("reviewer"),
            verdict=body.get("verdict"),
            grid=body.get("grid"),
            # `spans` is `[]` when there are none and never absent, so that "no
            # merges seen" stays distinguishable from "not asked" (§4).
            spans=body.get("spans") or [],
            notes=body.get("notes"),
            # `reviewed_at` is deliberately not taken from the request. It is
            # half of `review_id` (§4), and a client that can choose it can
            # choose which review it overwrites.
        )
    except reviews.ReviewRefused as exc:
        return _refused(exc)
    return 200, result


def dispatch(method: str, path: str, body: dict | None, *,
             conn, token: str | None, tokens: "set[str]") -> "tuple[int, dict]":
    """Route one request. Pure: no sockets, no printing, no global state.

    Auth is checked before routing, so an unauthenticated caller cannot map
    which paths exist, and -- acceptance 8 -- before `conn` is touched at all.
    """
    if not _authorized(token, tokens):
        return _error("error.unauthorized", "missing or unknown bearer token")

    route = path.split("?", 1)[0].split("#", 1)[0]
    if len(route) > 1:
        route = route.rstrip("/") or "/"

    if route == "/reviews":
        if method != "POST":
            return _error("error.method_not_allowed", f"{method} not allowed on {route}")
        return _post_review(body, conn=conn)

    if route == "/source-refs:batch":
        if method != "POST":
            return _error("error.method_not_allowed", f"{method} not allowed on {route}")
        return _post_batch(body, conn=conn)

    if route.startswith("/source-refs/"):
        ref_id = unquote(route[len("/source-refs/"):])
        if ref_id and "/" not in ref_id:
            if method != "GET":
                return _error("error.method_not_allowed",
                              f"{method} not allowed on {route}")
            return _get_source_ref(ref_id, conn=conn)

    # Everything else, including the other five Discovery and Authoring calls
    # of contract.md §1.5, which are out of scope for Phase 2 (spec §8).
    return _error("error.not_found", f"no route for {route}")


# --- transport -------------------------------------------------------------

def _open_conn():
    """One connection per request; sqlite3 objects belong to one thread.

    Factored out so the smoke test can drive `serve()` without a store.
    """
    from .store import connect

    return connect()


def _handler_class(tokens: "set[str]"):
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # Content-Length is set on every reply
        server_version = "fence-evidence"
        # StreamRequestHandler.timeout is None by default, so setup() never
        # calls settimeout and every read blocks forever. Measured: 120 sockets
        # sending ZERO bytes pinned 114 daemon threads for as long as the client
        # chose, unauthenticated, at a cost of one socket each.
        timeout = SOCKET_TIMEOUT_S

        def log_message(self, fmt, *args):  # noqa: D102 -- silence, not logging
            """The default writes a request line per request to stderr.

            This process runs behind Planning's backend under a supervisor that
            owns logging, and an unfiltered request line carries the ref ids
            being reviewed. Nothing here is diagnostic enough to be worth that.
            """

        def _respond(self, status: int, payload: dict) -> None:
            blob = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def _bearer(self) -> str | None:
            header = self.headers.get("Authorization", "")
            scheme, _, value = header.partition(" ")
            return value.strip() if scheme.lower() == "bearer" and value.strip() else None

        def _read_body(self) -> "tuple[bool, dict | None]":
            # RFC 9112 §6.3: a message carrying Transfer-Encoding must not be
            # framed by Content-Length. We honour only Content-Length, and the
            # deployment REQUIRES a fronting proxy (frontend -> Planning ->
            # here), so a front end that honours chunked while this server
            # honours Content-Length is a TE.CL desync: the declared body gets
            # re-parsed as the next request on a kept-alive connection.
            # Demonstrated -- a smuggled GET rode in behind a 401'd POST and was
            # answered 200. Refuse the combination rather than guess at framing.
            if self.headers.get("Transfer-Encoding"):
                return "unsupported", None
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return True, None
            if length > MAX_BODY_BYTES:
                return False, None
            if length <= 0:
                return True, None
            try:
                return True, json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                # Undecodable is malformed; the handler that owns the route
                # decides which code that is, so hand it a `None` body.
                return True, None

        def _handle(self, method: str) -> None:
            token = self._bearer()
            ok, body = self._read_body()
            if ok == "unsupported":
                self.close_connection = True     # never keep-alive a desync
                self._respond(*_error("error.malformed_request",
                                      "Transfer-Encoding is not supported; frame "
                                      "the body with Content-Length"))
                return
            if not ok:
                self._respond(*_error("error.request_too_large",
                                      f"request body exceeds {MAX_BODY_BYTES} bytes"))
                return
            # `_authorized` is reused only to decide whether to spend a file
            # handle: opening the store would create an empty database for an
            # unauthenticated caller. `dispatch` remains the sole authority on
            # the response, and answers 401 with `conn=None` untouched.
            conn = _open_conn() if _authorized(token, tokens) else None
            try:
                status, payload = dispatch(method, self.path, body,
                                           conn=conn, token=token, tokens=tokens)
            except Exception as exc:  # noqa: BLE001 -- a bug must not kill the thread
                # `dispatch` deliberately does not catch what it did not expect:
                # in the suite an unexpected exception should surface as itself.
                # A running server has to answer something, and 500 is that.
                status, payload = _error("error.internal", type(exc).__name__)
            finally:
                if conn is not None:
                    conn.close()
            self._respond(status, payload)

        def do_GET(self):  # noqa: N802 -- BaseHTTPRequestHandler's naming
            self._handle("GET")

        def do_POST(self):  # noqa: N802
            self._handle("POST")

        def do_PUT(self):  # noqa: N802
            self._handle("PUT")

        def do_DELETE(self):  # noqa: N802
            self._handle("DELETE")

        def do_PATCH(self):  # noqa: N802
            self._handle("PATCH")

    return Handler


def make_server(host: str, port: int, *, tokens: "set[str]"):
    """Build the server without running it, so a test can bind port 0 and stop it."""
    from http.server import ThreadingHTTPServer

    return ThreadingHTTPServer((host, port), _handler_class(tokens))


def serve(host: str, port: int, *, tokens: "set[str]") -> None:
    """Run until interrupted. Everything it does is `dispatch` plus JSON."""
    server = make_server(host, port, tokens=tokens)
    try:
        server.serve_forever()
    finally:
        server.server_close()
