from __future__ import annotations

from typing import Any, Dict

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class SystemStatusPlugin(BasePlugin):
    """Placeholder status plugin (Phase 1 stub)."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"status": {"description": "Report CPU/RAM/disk"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "status":
            raise ExecutionError(f"Unknown status action '{action}'")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"cpu": "n/a", "ram": "n/a", "disk": "n/a"}
