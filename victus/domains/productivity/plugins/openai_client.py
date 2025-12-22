from __future__ import annotations

from typing import Any, Dict

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class OpenAIClientPlugin(BasePlugin):
    """Stub OpenAI client that only drafts text when approved."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"draft": {"description": "Draft text using OpenAI"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "draft":
            raise ExecutionError(f"Unknown openai action '{action}'")
        if "prompt" not in args:
            raise ExecutionError("'prompt' argument is required")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"draft": f"drafted: {args.get('prompt')}"}
