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
