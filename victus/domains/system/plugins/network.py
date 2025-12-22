from __future__ import annotations

from typing import Any, Dict

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class SystemNetworkPlugin(BasePlugin):
    """Placeholder network snapshot plugin (Phase 1 stub)."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"net_snapshot": {"description": "Return basic network info"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "net_snapshot":
            raise ExecutionError(f"Unknown network action '{action}'")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"interfaces": []}
