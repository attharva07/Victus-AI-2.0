from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Optional

from .config import ServerSettings


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    email: str
    password_hash: str
    is_admin: bool
    created_at: str
    mfa_secret: Optional[str]
    mfa_enabled: bool


class Database:
    def __init__(self, settings: ServerSettings) -> None:
        self.settings = settings
        self._db_path = self._parse_sqlite_path(settings.database_url)
        self._ensure_parent()
        self._init_db()

    def _parse_sqlite_path(self, database_url: str) -> Path:
        if not database_url.startswith("sqlite"):
            raise ValueError("Only sqlite database URLs are supported in server-mode")
        if database_url.startswith("sqlite:///"):
            return Path(database_url.replace("sqlite:///", "/", 1)).expanduser()
        if database_url.startswith("sqlite://"):
            return Path(database_url.replace("sqlite://", "", 1)).expanduser()
        if database_url.startswith("sqlite:"):
            return Path(database_url.replace("sqlite:", "", 1)).expanduser()
        raise ValueError("Invalid sqlite database URL")

    def _ensure_parent(self) -> None:
        if self._db_path.parent:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    mfa_secret TEXT,
                    mfa_enabled INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def create_user(self, user: UserRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, is_admin, created_at, mfa_secret, mfa_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.email,
                    user.password_hash,
                    1 if user.is_admin else 0,
                    user.created_at,
                    user.mfa_secret,
                    1 if user.mfa_enabled else 0,
                ),
            )

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, is_admin, created_at, mfa_secret, mfa_enabled FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return self._row_to_user(row)

    def get_user_by_id(self, user_id: str) -> Optional[UserRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, is_admin, created_at, mfa_secret, mfa_enabled FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(row)

    def count_users(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
        return int(row["count"]) if row else 0

    def update_mfa_secret(self, user_id: str, mfa_secret: Optional[str]) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET mfa_secret = ? WHERE id = ?", (mfa_secret, user_id))

    def set_mfa_enabled(self, user_id: str, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET mfa_enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))

    def _row_to_user(self, row: sqlite3.Row | None) -> Optional[UserRecord]:
        if row is None:
            return None
        return UserRecord(
            user_id=row["id"],
            email=row["email"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=row["created_at"],
            mfa_secret=row["mfa_secret"],
            mfa_enabled=bool(row["mfa_enabled"]),
        )
