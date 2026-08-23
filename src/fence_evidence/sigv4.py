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
