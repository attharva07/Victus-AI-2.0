from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List

import json

from victus.app import VictusApp
from victus.core.schemas import TurnEvent
from victus.memory.gate import MemoryGate
from victus.memory.models import MemoryRecord
from victus.memory.search import MemorySearch
from victus.memory.store import MemoryStore

from .memory_store_v2 import VictusMemory, VictusMemoryStore

class TurnHandler:
    def __init__(
        self,
        app: VictusApp,
        store: MemoryStore | None = None,
        memory_store_v2: VictusMemoryStore | None = None,
    ) -> None:
        self.app = app
        self.store = store or MemoryStore()
        self.search = MemorySearch(self.store)
        self.gate = MemoryGate()
        self.memory_store_v2 = memory_store_v2 or VictusMemoryStore()

    async def run_turn(self, message: str) -> AsyncIterator[TurnEvent]:
        memory_hits = self.search.search(message, top_k=3)
        if memory_hits:
            yield TurnEvent(
                event="memory_used",
                result={
                    "count": len(memory_hits),
                    "ids": [record.id for record in memory_hits],
                    "items": [self._to_summary(record) for record in memory_hits],
                },
            )

        memory_prompt = self._format_v2_memory_prompt(message)
        streamed_text = ""
        async for event in self.app.run_request(message, memory_prompt=memory_prompt):
            if event.event == "token" and event.token:
                streamed_text += event.token
            yield event

        candidate = self._extract_memory_candidate(streamed_text)
        if candidate:
            yield TurnEvent(event="memory_candidate", result={"memory_candidate": candidate})

        record = self._maybe_write_memory(message)
        if record:
            yield TurnEvent(
                event="memory_written",
                result=self._to_summary(record),
            )

    def _maybe_write_memory(self, message: str) -> MemoryRecord | None:
        candidate = self.gate.extract_candidate(message, source="user")
        if not candidate:
            return None
        record = self.gate.build_record(candidate)
        self.store.append(record)
        return record

    @staticmethod
    def _format_memory_prompt(records: List[MemoryRecord]) -> str:
        if not records:
            return ""
        lines = ["Relevant memory:"]
        for record in records:
            lines.append(f"- ({record.kind}) {record.text}")
        return "\n".join(lines)

    def _format_v2_memory_prompt(self, message: str) -> str:
        memories = self.memory_store_v2.search(message, limit=5)
        if not memories:
            return ""
        lines = ["Relevant memory:"]
        for memory in memories:
            lines.append(f"- ({memory.type}) {memory.content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_memory_candidate(text: str) -> Dict[str, Any] | None:
        for payload in _extract_json_payloads(text):
            candidate = payload.get("memory_candidate")
            if not isinstance(candidate, dict):
                continue
            try:
                memory = VictusMemory(**candidate)
            except Exception:
                continue
            return memory.model_dump()
        return None

    @staticmethod
    def _merge_memory_prompts(v1_prompt: str, v2_prompt: str) -> str:
        prompts = [prompt for prompt in [v1_prompt, v2_prompt] if prompt.strip()]
        return "\n\n".join(prompts)

    def _format_v2_memory_prompt(self, message: str) -> str:
        memories = self.memory_store_v2.search(message, limit=5)
        if not memories:
            return ""
        lines = ["Relevant memory:"]
        for memory in memories:
            lines.append(f"- ({memory.type}) {memory.content}")
        return "\n".join(lines)

    @staticmethod
    def _extract_memory_candidate(text: str) -> Dict[str, Any] | None:
        for payload in _extract_json_payloads(text):
            candidate = payload.get("memory_candidate")
            if not isinstance(candidate, dict):
                continue
            try:
                memory = VictusMemory(**candidate)
            except Exception:
                continue
            return memory.model_dump()
        return None

    @staticmethod
    def _to_summary(record: MemoryRecord) -> dict:
        return {
            "id": record.id,
            "ts": record.ts,
            "scope": record.scope,
            "kind": record.kind,
            "text": record.text,
            "tags": record.tags,
            "source": record.source,
            "confidence": record.confidence,
            "pii_risk": record.pii_risk,
        }


def _extract_json_payloads(text: str) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    stack = 0
    start_index = None
    for index, char in enumerate(text):
        if char == "{":
            if stack == 0:
                start_index = index
            stack += 1
        elif char == "}":
            if stack == 0:
                continue
            stack -= 1
            if stack == 0 and start_index is not None:
                snippet = text[start_index : index + 1]
                try:
                    payloads.append(json.loads(snippet))
                except json.JSONDecodeError:
                    pass
                start_index = None
    return payloads
