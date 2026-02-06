from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from core.logging.logger import get_logger


def safe_excerpt(value: str, *, max_len: int = 80) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_len:
        return compact
    return f"{compact[:max_len]}..."


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def audit_event(event: str, **fields: Any) -> None:
    logger = get_logger()
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    payload = {"event": event, "timestamp": timestamp, **fields}
    logger.info("audit %s", payload)
