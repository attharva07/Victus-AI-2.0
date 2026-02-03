from __future__ import annotations

from core.orchestrator.schemas import Intent

_ALLOWED_ACTIONS = {
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
}


def validate_intent(intent: Intent) -> Intent:
    if intent.action not in _ALLOWED_ACTIONS:
        return Intent(action="noop", parameters={}, confidence=0.0)
    return intent
