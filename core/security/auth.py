from __future__ import annotations

import base64
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status

from core.config import ensure_directories
from core.logging.audit import audit_event


@dataclass(frozen=True)
class AdminAccount:
    username: str
    password_hash: str


@dataclass(frozen=True)
class TokenPayload:
    sub: str
    iat: int
    exp: int


def _admin_file() -> Path:
    paths = ensure_directories()
    return paths.data_dir / "admin.json"


def _token_secret_file() -> Path:
    paths = ensure_directories()
    return paths.data_dir / "token_secret"


def _load_or_create_admin() -> AdminAccount:
    admin_path = _admin_file()
    if admin_path.exists():
        data = json.loads(admin_path.read_text())
        return AdminAccount(username=data["username"], password_hash=data["password_hash"])
    username = os.getenv("VICTUS_LOCAL_ADMIN_USERNAME", "admin")
    password = os.getenv("VICTUS_LOCAL_ADMIN_PASSWORD", "admin")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    admin_path.write_text(json.dumps({"username": username, "password_hash": password_hash}))
    return AdminAccount(username=username, password_hash=password_hash)


def _load_or_create_secret() -> str:
    secret_path = _token_secret_file()
    if secret_path.exists():
        return secret_path.read_text().strip()
    secret = secrets.token_urlsafe(32)
    secret_path.write_text(secret)
    return secret


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate(username: str, password: str) -> bool:
    account = _load_or_create_admin()
    return username == account.username and verify_password(password, account.password_hash)


def _encode_payload(payload: TokenPayload, secret: str) -> str:
    payload_json = json.dumps(payload.__dict__).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b"=").decode("utf-8")
    signature = bcrypt.kdf(
        password=payload_b64.encode("utf-8"),
        salt=secret.encode("utf-8"),
        desired_key_bytes=32,
        rounds=64,
    )
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")
    return f"{payload_b64}.{signature_b64}"


def _decode_payload(token: str, secret: str) -> Optional[TokenPayload]:
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None
    expected_signature = bcrypt.kdf(
        password=payload_b64.encode("utf-8"),
        salt=secret.encode("utf-8"),
        desired_key_bytes=32,
        rounds=64,
    )
    expected_b64 = base64.urlsafe_b64encode(expected_signature).rstrip(b"=").decode("utf-8")
    if not secrets.compare_digest(expected_b64, signature_b64):
        return None
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload_raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    data = json.loads(payload_raw)
    return TokenPayload(sub=data["sub"], iat=data["iat"], exp=data["exp"])


def create_token(username: str, expires_in: int = 3600) -> str:
    now = int(time.time())
    payload = TokenPayload(sub=username, iat=now, exp=now + expires_in)
    secret = _load_or_create_secret()
    return _encode_payload(payload, secret)


def verify_token(token: str) -> Optional[TokenPayload]:
    secret = _load_or_create_secret()
    payload = _decode_payload(token, secret)
    if payload is None:
        return None
    if payload.exp < int(time.time()):
        return None
    return payload


def get_current_user(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    token = auth_header.split(" ", 1)[1].strip()
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return payload.sub


def require_user(user: str = Depends(get_current_user)) -> str:
    return user


def login_user(username: str, password: str) -> str:
    if not authenticate(username, password):
        audit_event("auth_failed", username=username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    audit_event("auth_success", username=username)
    return create_token(username)
