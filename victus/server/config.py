from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ServerSettings:
    database_url: str
    token_secret: str
    token_ttl_seconds: int
    cors_allow_origins: list[str]
    allow_registration: bool
    mfa_secret_key: str
    rate_limit_per_minute: int
    rate_limit_window_seconds: int
    version: str


def get_settings() -> ServerSettings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///victus_data/server.db").strip()
    token_secret = os.getenv("TOKEN_SECRET", "dev-insecure-change-me").strip()
    cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    cors_allow_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
    if "*" in cors_allow_origins:
        raise ValueError("CORS_ALLOW_ORIGINS must not include wildcard '*'")
    allow_registration = _env_bool("ALLOW_REGISTRATION", True)
    mfa_secret_key = os.getenv("MFA_SECRET_KEY", token_secret).strip()
    rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    version = os.getenv("VICTUS_VERSION", "0.1.0-server")
    return ServerSettings(
        database_url=database_url,
        token_secret=token_secret,
        token_ttl_seconds=int(os.getenv("TOKEN_TTL_SECONDS", "3600")),
        cors_allow_origins=cors_allow_origins,
        allow_registration=allow_registration,
        mfa_secret_key=mfa_secret_key,
        rate_limit_per_minute=rate_limit_per_minute,
        rate_limit_window_seconds=rate_limit_window_seconds,
        version=version,
    )
