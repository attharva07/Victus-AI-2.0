from __future__ import annotations

from typing import Any, Dict

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class SystemAppsPlugin(BasePlugin):
    """Placeholder app launcher plugin (Phase 1 stub)."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"open_app": {"description": "Open allowlisted applications"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "open_app":
            raise ExecutionError(f"Unknown app action '{action}'")
        if "app" not in args:
            raise ExecutionError("'app' argument is required")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"opened": args.get("app")}
