from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

import bcrypt


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def create_access_token(payload: Dict[str, Any], secret: str) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"v1.{payload_b64}.{signature_b64}"


def verify_access_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    try:
        version, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError:
        return None
    if version != "v1":
        return None
    expected = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except json.JSONDecodeError:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < int(time.time()):
        return None
    return payload


def build_token_payload(user_id: str, email: str, ttl_seconds: int) -> Dict[str, Any]:
    now = int(time.time())
    return {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + ttl_seconds,
    }


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def _derive_stream(key: str, length: int) -> bytes:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    stream = digest
    while len(stream) < length:
        digest = hashlib.sha256(digest).digest()
        stream += digest
    return stream[:length]


def encode_totp_secret(secret: str, key: str) -> str:
    secret_bytes = secret.encode("utf-8")
    stream = _derive_stream(key, len(secret_bytes))
    obfuscated = bytes(a ^ b for a, b in zip(secret_bytes, stream))
    return base64.urlsafe_b64encode(obfuscated).decode("utf-8")


def decode_totp_secret(encoded: str, key: str) -> str:
    secret_bytes = base64.urlsafe_b64decode(encoded.encode("utf-8"))
    stream = _derive_stream(key, len(secret_bytes))
    decoded = bytes(a ^ b for a, b in zip(secret_bytes, stream))
    return decoded.decode("utf-8")


def _totp_at(secret: str, for_time: int, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int(for_time / step)
    msg = counter.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    if not code.isdigit():
        return False
    now = int(time.time())
    for offset in range(-window, window + 1):
        if _totp_at(secret, now + offset * 30) == code:
            return True
    return False
