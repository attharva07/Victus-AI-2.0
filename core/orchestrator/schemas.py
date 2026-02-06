from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    utterance: str | None = Field(default=None, min_length=1)
    text: str | None = Field(default=None, min_length=1)
    domain: str | None = None
    context: Dict[str, Any] = Field(default_factory=dict)

    def normalized_text(self) -> str:
        if self.text:
            return self.text
        if self.utterance:
            return self.utterance
        raise ValueError("Either 'text' or 'utterance' is required.")


class Intent(BaseModel):
    action: Literal[
        "noop",
        "camera.status",
        "camera.capture",
        "camera.recognize",
        "memory.add",
        "memory.search",
        "memory.list",
        "memory.delete",
        "finance.add_transaction",
        "finance.list_transactions",
        "finance.summary",
        "files.list",
        "files.read",
        "files.write",
    ]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ActionResult(BaseModel):
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] | None = None


class OrchestrateResponse(BaseModel):
    intent: Intent
    message: str
    actions: List[ActionResult] = Field(default_factory=list)
    mode: Literal["deterministic", "llm_proposal"] = "deterministic"
    proposed_action: Dict[str, Any] | None = None
    executed: bool = True
    result: Dict[str, Any] | None = None


class OrchestrateErrorResponse(BaseModel):
    error: Literal["clarify", "unknown_intent"]
    message: str
    fields: Dict[str, Any] | None = None
    candidates: List[str] | None = None
