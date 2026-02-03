from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.logging.logger import get_logger


def audit_event(event: str, **fields: Any) -> None:
    logger = get_logger()
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    payload = {"event": event, "timestamp": timestamp, **fields}
    logger.info("audit %s", payload)
