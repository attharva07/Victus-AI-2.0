from __future__ import annotations

from typing import Optional

from core.orchestrator.schemas import Intent, OrchestrateRequest


class LLMProvider:
    def propose_intent(self, request: OrchestrateRequest) -> Optional[Intent]:
        return None
