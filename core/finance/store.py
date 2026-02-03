from __future__ import annotations

from typing import Any

from core.storage.db import get_connection


def _row_to_transaction(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ts": row["ts"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "category": row["category"],
        "merchant": row["merchant"],
        "note": row["note"],
        "method": row["method"],
        "source": row["source"],
    }


def add_transaction(record: dict[str, Any]) -> str:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transactions (
                id, ts, amount_cents, currency, category, merchant, note, method, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["ts"],
                record["amount_cents"],
                record["currency"],
                record["category"],
                record["merchant"],
                record["note"],
                record["method"],
                record["source"],
            ),
        )
    return record["id"]


def list_transactions(
    start_ts: str | None,
    end_ts: str | None,
    category: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list[Any] = []
    if start_ts:
        sql += " AND ts >= ?"
        params.append(start_ts)
    if end_ts:
        sql += " AND ts <= ?"
        params.append(end_ts)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_transaction(row) for row in rows]


def summarize_transactions(
    start_ts: str | None,
    end_ts: str | None,
    group_by: str,
) -> dict[str, int]:
    if group_by not in {"category"}:
        group_by = "category"
    sql = f"SELECT {group_by} as key, SUM(amount_cents) as total FROM transactions WHERE 1=1"
    params: list[Any] = []
    if start_ts:
        sql += " AND ts >= ?"
        params.append(start_ts)
    if end_ts:
        sql += " AND ts <= ?"
        params.append(end_ts)
    sql += f" GROUP BY {group_by}"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {row["key"]: row["total"] for row in rows if row["key"] is not None}
