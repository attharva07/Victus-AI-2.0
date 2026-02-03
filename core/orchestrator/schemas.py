from __future__ import annotations

from typing import Any, Dict, Literal, List

from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    utterance: str = Field(..., min_length=1)


class Intent(BaseModel):
    action: Literal[
        "noop",
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
