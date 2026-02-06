from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProposalResult(BaseModel):
    ok: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    action: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str = "llm_proposer_stub"
    raw: dict[str, Any] | None = None


class LLMProposer:
    def propose(
        self,
        text: str,
        domain: str | None,
        candidates: list[str],
        context: dict[str, Any],
    ) -> ProposalResult:
        _ = (text, domain, candidates, context)
        return ProposalResult(ok=False, confidence=0.0, reason="llm_disabled_or_stub")


class StubLLMProposer(LLMProposer):
    pass


# Backwards-compatible alias used by existing imports.
class LLMProvider(StubLLMProposer):
    def propose_intent(self, request: Any) -> None:
        _ = request
        return None
