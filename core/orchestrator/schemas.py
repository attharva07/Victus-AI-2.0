from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    utterance: str = Field(..., min_length=1)


class Intent(BaseModel):
    action: Literal["noop"]
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OrchestrateResponse(BaseModel):
    intent: Intent
    message: str
