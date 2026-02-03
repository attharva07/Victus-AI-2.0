from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from core.logging.audit import audit_event
from core.memory import store


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []
    return [tag.strip() for tag in tags if tag and tag.strip()]


def add_memory(
    content: str,
    type: str = "note",
    tags: Iterable[str] | None = None,
    source: str = "user",
    importance: int = 5,
    confidence: float = 0.8,
) -> str:
    memory_id = str(uuid4())
    ts = datetime.now(tz=timezone.utc).isoformat()
    normalized_tags = _normalize_tags(tags)
    record = {
        "id": memory_id,
        "ts": ts,
        "type": type,
        "tags": json.dumps(normalized_tags),
        "source": source,
        "content": content,
        "importance": importance,
        "confidence": confidence,
    }
    store.add_memory(record)
    audit_event(
        "memory_added",
        memory_id=memory_id,
        memory_type=type,
        tags=normalized_tags,
        source=source,
    )
    return memory_id


def search_memories(query: str, tags: Iterable[str] | None, limit: int = 10) -> list[dict[str, object]]:
    normalized_tags = _normalize_tags(tags)
    results = store.search_memories(query, normalized_tags, limit)
    audit_event("memory_searched", query=query, tags=normalized_tags, limit=limit)
    return results


def list_recent(limit: int = 20) -> list[dict[str, object]]:
    results = store.list_recent(limit)
    audit_event("memory_listed", limit=limit)
    return results


def delete_memory(memory_id: str) -> bool:
    deleted = store.delete_memory(memory_id)
    audit_event("memory_deleted", memory_id=memory_id, deleted=deleted)
    return deleted
