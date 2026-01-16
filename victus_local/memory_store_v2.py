from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class VictusMemory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    content: str
    source: str
    confidence: float = 0.7
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_used_at: Optional[str] = None
    pinned: bool = False


class VictusMemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("victus_data") / "memory" / "victus_memory.json"
        self._ensure_path()

    def _ensure_path(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load(self) -> List[VictusMemory]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            payload = []
        return [VictusMemory(**item) for item in payload]

    def _save(self, memories: List[VictusMemory]) -> None:
        payload = [memory.model_dump() for memory in memories]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> List[VictusMemory]:
        memories = self._load()
        memories.sort(key=lambda memory: memory.created_at, reverse=True)
        return memories

    def upsert(self, memory: VictusMemory) -> VictusMemory:
        memories = self._load()
        for index, existing in enumerate(memories):
            if existing.id == memory.id:
                memories[index] = memory
                self._save(memories)
                return memory
        memories.append(memory)
        self._save(memories)
        return memory

    def delete(self, memory_id: str) -> bool:
        memories = self._load()
        filtered = [memory for memory in memories if memory.id != memory_id]
        if len(filtered) == len(memories):
            return False
        self._save(filtered)
        return True

    def search(self, query: str, limit: int = 5) -> List[VictusMemory]:
        tokens = {token for token in re.split(r"\W+", query.lower()) if token}
        if not tokens:
            return []
        scored: List[tuple[int, VictusMemory]] = []
        for memory in self._load():
            content = memory.content.lower()
            score = sum(1 for token in tokens if token in content)
            if score > 0:
                scored.append((score, memory))
        scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        selected = [memory for _, memory in scored[:limit]]
        if selected:
            now = datetime.utcnow().isoformat() + "Z"
            updated = self._load()
            memory_map = {memory.id: memory for memory in updated}
            for memory in selected:
                if memory.id in memory_map:
                    memory_map[memory.id].last_used_at = now
            self._save(list(memory_map.values()))
        return selected
