from __future__ import annotations

from typing import Any, Dict

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class DocWriterPlugin(BasePlugin):
    """Stub document writer plugin."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"create": {"description": "Create a local document"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "create":
            raise ExecutionError(f"Unknown doc action '{action}'")
        if "title" not in args:
            raise ExecutionError("'title' argument is required")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"doc": args.get("title")}
