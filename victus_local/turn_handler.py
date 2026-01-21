from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import json

from victus.app import VictusApp
from victus.core.schemas import Context, Plan, PlanStep, TurnEvent
from victus.memory.gate import MemoryGate
from victus.memory.models import MemoryRecord
from victus.memory.search import MemorySearch
from victus.memory.store import MemoryStore

from .app_aliases import build_clarify_message, load_alias_store, resolve_candidate_choice
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
        self.pending_action: Optional[Dict[str, Any]] = None

    async def run_turn(self, message: str) -> AsyncIterator[TurnEvent]:
        pending = self.pending_action
        if pending and pending.get("intent") == "local.open_app":
            resolved = self._resolve_pending_open_app(message, pending)
            if resolved:
                original = str(pending.get("original") or "")
                self.pending_action = None
                async for event in self._run_pending_open_app(message, resolved, original):
                    yield event
                return
            clarify_message = build_clarify_message(pending.get("candidates") or [])
            yield TurnEvent(event="status", status="done")
            yield TurnEvent(event="clarify", message=clarify_message)
            return

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
            if event.event == "tool_done" and event.action == "open_app":
                self._maybe_store_pending_action(event)
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

    def _maybe_store_pending_action(self, event: TurnEvent) -> None:
        result = event.result or {}
        if not isinstance(result, dict):
            return
        if result.get("decision") != "clarify":
            return
        candidates = result.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            return
        self.pending_action = {
            "intent": "local.open_app",
            "candidates": candidates,
            "missing_field": "app_name",
            "original": result.get("original") or "",
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

    @staticmethod
    def _resolve_pending_open_app(message: str, pending: Dict[str, Any]) -> Optional[Dict[str, str]]:
        candidates = pending.get("candidates") or []
        if not isinstance(candidates, list) or not candidates:
            return None
        alias_store = load_alias_store()
        aliases = alias_store.get("aliases", {}) if isinstance(alias_store, dict) else {}
        if not isinstance(aliases, dict):
            aliases = {}
        return resolve_candidate_choice(message, candidates, aliases)

    async def _run_pending_open_app(
        self,
        message: str,
        resolved: Dict[str, str],
        original_alias: str,
    ) -> AsyncIterator[TurnEvent]:
        plan = Plan(
            goal=message,
            domain="productivity",
            steps=[
                PlanStep(
                    id="step-1",
                    tool="local",
                    action="open_app",
                    args={"name": resolved["target"], "requested_alias": original_alias},
                )
            ],
            risk="low",
            origin="router",
        )
        context = self.app.context_factory() if self.app.context_factory else Context(
            session_id="victus-session",
            timestamp=datetime.utcnow(),
            mode="dev",
            foreground_app=None,
        )

        yield TurnEvent(event="status", status="thinking")
        confidence = self.app._evaluate_confidence(plan)
        if confidence.decision == "clarify":
            yield TurnEvent(event="status", status="done")
            yield TurnEvent(event="clarify", message=self.app.confidence_engine.build_clarification(confidence.primary))
            return
        if confidence.decision == "block":
            yield TurnEvent(event="status", status="denied")
            yield TurnEvent(event="error", message=self.app.confidence_engine.build_block_message(confidence.primary))
            return

        prepared_plan, approval = self.app.request_approval(plan, context)
        yield TurnEvent(event="status", status="executing")
        for step in prepared_plan.steps:
            yield TurnEvent(
                event="tool_start",
                tool=step.tool,
                action=step.action,
                args=step.args,
                step_id=step.id,
            )

        results = await asyncio.to_thread(self.app.execute_plan_streaming, prepared_plan, approval)
        error_messages = []
        assistant_messages = []
        for step in prepared_plan.steps:
            result = results.get(step.id)
            if isinstance(result, dict) and result.get("error"):
                error_messages.append(str(result["error"]))
            if isinstance(result, dict):
                assistant_message = result.get("assistant_message")
                if isinstance(assistant_message, str) and assistant_message.strip():
                    assistant_messages.append(assistant_message.strip())
            yield TurnEvent(
                event="tool_done",
                tool=step.tool,
                action=step.action,
                result=result,
                step_id=step.id,
            )

        if assistant_messages:
            combined = "\n".join(assistant_messages)
            yield TurnEvent(event="token", token=combined, step_id=prepared_plan.steps[0].id)

        if error_messages:
            yield TurnEvent(event="status", status="error")
            yield TurnEvent(event="error", message=error_messages[0])
        else:
            yield TurnEvent(event="status", status="done")

        self.app.audit.log_request(
            user_input=message,
            plan=prepared_plan,
            approval=approval,
            results=results,
            errors="; ".join(error_messages) if error_messages else None,
        )


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
