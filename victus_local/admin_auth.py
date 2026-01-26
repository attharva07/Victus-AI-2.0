"""Admin authentication utilities for the local Victus server."""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import base64
import binascii
import hashlib
import hmac
import importlib
import importlib.util


class AdminAuthManager:
    def __init__(self, credentials_path: Path | None = None, ttl_seconds: int = 900) -> None:
        self.credentials_path = credentials_path or Path(__file__).parent / "admin_credentials.json"
        self.ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[str, datetime] = {}
        self._password_hash = self._load_password_hash()

    def verify_password(self, password: str) -> bool:
        if not password:
            return False
        if self._password_hash.startswith("pbkdf2$"):
            return _verify_pbkdf2(password, self._password_hash)
        if _BCRYPT is None:
            return False
        return _BCRYPT.checkpw(password.encode("utf-8"), self._password_hash.encode("utf-8"))

    def issue_session(self) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + self.ttl
        self._sessions[token] = expires_at
        return token, expires_at

    def revoke_session(self, token: Optional[str]) -> None:
        if not token:
            return
        self._sessions.pop(token, None)

    def is_session_valid(self, token: Optional[str]) -> bool:
        if not token:
            return False
        expires_at = self._sessions.get(token)
        if not expires_at:
            return False
        if datetime.utcnow() >= expires_at:
            self._sessions.pop(token, None)
            return False
        return True

    def _load_password_hash(self) -> str:
        env_hash = _load_env_hash()
        if env_hash:
            return env_hash
        if not self.credentials_path.exists():
            return self._write_default_credentials()
        try:
            payload = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._write_default_credentials()
        stored = payload.get("password_hash")
        if isinstance(stored, str) and stored:
            return stored
        return self._write_default_credentials()

    def _write_default_credentials(self) -> str:
        default_hash = _hash_password("victus")
        payload = {"password_hash": default_hash}
        self.credentials_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return default_hash


def _load_env_hash() -> Optional[str]:
    env_value = os.getenv("ADMIN_PASSWORD_HASH")
    if not env_value:
        return None
    return env_value


_BCRYPT_SPEC = importlib.util.find_spec("bcrypt")
_BCRYPT = importlib.import_module("bcrypt") if _BCRYPT_SPEC else None


def _hash_password(password: str) -> str:
    if _BCRYPT is not None:
        hashed = _BCRYPT.hashpw(password.encode("utf-8"), _BCRYPT.gensalt())
        return hashed.decode("utf-8")
    return _hash_pbkdf2(password)


def _hash_pbkdf2(password: str, iterations: int = 120_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("utf-8"),
        base64.b64encode(digest).decode("utf-8"),
    )


def _verify_pbkdf2(password: str, encoded: str) -> bool:
    try:
        _, iterations_str, salt_b64, digest_b64 = encoded.split("$", 3)
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(digest_b64.encode("utf-8"))
    except (ValueError, TypeError, binascii.Error):
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(computed, expected)
