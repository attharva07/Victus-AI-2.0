from __future__ import annotations

import json
from typing import Any, Iterable

from core.storage.db import get_connection


def _row_to_memory(row: Any) -> dict[str, Any]:
    tags_raw = row["tags"] or "[]"
    try:
        tags = json.loads(tags_raw)
    except json.JSONDecodeError:
        tags = [tag for tag in tags_raw.split(",") if tag]
    return {
        "id": row["id"],
        "ts": row["ts"],
        "type": row["type"],
        "tags": tags,
        "source": row["source"],
        "content": row["content"],
        "importance": row["importance"],
        "confidence": row["confidence"],
    }


def add_memory(record: dict[str, Any]) -> str:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO memories (id, ts, type, tags, source, content, importance, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["ts"],
                record["type"],
                record["tags"],
                record["source"],
                record["content"],
                record["importance"],
                record["confidence"],
            ),
        )
    return record["id"]


def search_memories(query: str, tags: Iterable[str] | None, limit: int) -> list[dict[str, Any]]:
    sql = "SELECT * FROM memories WHERE 1=1"
    params: list[Any] = []
    if query:
        sql += " AND content LIKE ?"
        params.append(f"%{query}%")
    if tags:
        for tag in tags:
            sql += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_memory(row) for row in rows]


def list_recent(limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_memory(row) for row in rows]


def delete_memory(memory_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        deleted = cursor.rowcount > 0
    return deleted
