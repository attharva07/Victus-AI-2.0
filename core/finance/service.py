from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from core.finance import store
from core.logging.audit import audit_event


def add_transaction(
    amount_cents: int,
    currency: str = "USD",
    category: str = "uncategorized",
    merchant: str | None = None,
    note: str | None = None,
    method: str | None = None,
    ts: str | None = None,
    source: str = "user",
) -> str:
    ts_value = ts or datetime.now(tz=timezone.utc).isoformat()
    transaction_id = str(uuid4())
    record = {
        "id": transaction_id,
        "ts": ts_value,
        "amount_cents": amount_cents,
        "currency": currency,
        "category": category,
        "merchant": merchant,
        "note": note,
        "method": method,
        "source": source,
    }
    store.add_transaction(record)
    audit_event(
        "finance_transaction_added",
        transaction_id=transaction_id,
        amount_cents=amount_cents,
        currency=currency,
        category=category,
        merchant=merchant,
        method=method,
        source=source,
    )
    return transaction_id


def list_transactions(
    start_ts: str | None = None,
    end_ts: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    results = store.list_transactions(start_ts, end_ts, category, limit)
    audit_event(
        "finance_transactions_listed",
        start_ts=start_ts,
        end_ts=end_ts,
        category=category,
        limit=limit,
    )
    return results


def _period_bounds(period: str, start_ts: str | None, end_ts: str | None) -> tuple[str | None, str | None]:
    now = datetime.now(tz=timezone.utc)
    if period == "week":
        start = now - timedelta(days=7)
        return start.isoformat(), now.isoformat()
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.isoformat(), now.isoformat()
    if period == "custom":
        return start_ts, end_ts
    return None, None


def summary(
    period: str = "week",
    start_ts: str | None = None,
    end_ts: str | None = None,
    group_by: str = "category",
) -> dict[str, Any]:
    start, end = _period_bounds(period, start_ts, end_ts)
    totals = store.summarize_transactions(start, end, group_by)
    report = {"period": period, "start_ts": start, "end_ts": end, "group_by": group_by, "totals": totals}
    audit_event(
        "finance_summary_requested",
        period=period,
        start_ts=start,
        end_ts=end,
        group_by=group_by,
    )
    return report
