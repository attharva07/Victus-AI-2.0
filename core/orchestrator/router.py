from __future__ import annotations

from adapters.llm.provider import LLMProvider
from core.orchestrator.policy import validate_intent
from core.orchestrator.schemas import Intent, OrchestrateRequest, OrchestrateResponse


def _deterministic_route(_: OrchestrateRequest) -> Intent:
    return Intent(action="noop", parameters={}, confidence=1.0)


def route_intent(request: OrchestrateRequest, llm_provider: LLMProvider) -> OrchestrateResponse:
    intent = _deterministic_route(request)
    if intent is None:
        proposed = llm_provider.propose_intent(request)
        if proposed is None:
            intent = Intent(action="noop", parameters={}, confidence=0.0)
        else:
            intent = proposed
    intent = validate_intent(intent)
    message = "Phase 1 scaffold: no actions executed."
    return OrchestrateResponse(intent=intent, message=message)
