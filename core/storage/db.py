from __future__ import annotations

import sqlite3
from pathlib import Path

from core.config import ensure_directories

_DB_INITIALIZED: set[Path] = set()


def get_db_path() -> Path:
    paths = ensure_directories()
    return paths.data_dir / "victus_local.sqlite3"


def init_db() -> None:
    db_path = get_db_path()
    if db_path in _DB_INITIALIZED:
        return
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                ts TEXT,
                type TEXT,
                tags TEXT,
                source TEXT,
                content TEXT,
                importance INTEGER,
                confidence REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                ts TEXT,
                amount_cents INTEGER,
                currency TEXT,
                category TEXT,
                merchant TEXT,
                note TEXT,
                method TEXT,
                source TEXT
            )
            """
        )
        conn.commit()
        _DB_INITIALIZED.add(db_path)
    finally:
        conn.close()


def get_connection() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn
