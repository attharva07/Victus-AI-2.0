from __future__ import annotations

from typing import Any, Dict

from ..core.schemas import Approval, ExecutionError


class BasePlugin:
    """Base interface all plugins must implement."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        raise NotImplementedError

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        raise NotImplementedError

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        raise NotImplementedError


class DummyPlugin(BasePlugin):
    def __init__(self, allowed_actions):
        self.allowed_actions = set(allowed_actions)

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {action: {} for action in self.allowed_actions}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action not in self.allowed_actions:
            raise ExecutionError(f"Unknown action '{action}' for plugin")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"action": action, "args": args}
