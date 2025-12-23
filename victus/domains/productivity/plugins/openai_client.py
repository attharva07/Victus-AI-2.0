from __future__ import annotations

from typing import Any, Dict, Optional

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class OpenAIClientStub:
    def draft_email(self, *, to: str, subject: str, body: str) -> Dict[str, str]:
        return {"action": "draft_email", "to": to, "subject": subject, "body": body}

    def summarize_text(self, *, text: str) -> Dict[str, str]:
        return {"action": "summarize_text", "summary": text[:200] if text else ""}


class OpenAIClientPlugin(BasePlugin):
    """Stub OpenAI client that drafts or summarizes text when approved."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client or OpenAIClientStub()

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "draft": {"description": "Draft text using OpenAI"},
            "draft_email": {"description": "Draft an email body"},
            "summarize_text": {"description": "Summarize provided text"},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action == "draft":
            if not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
                raise ExecutionError("'prompt' argument is required")
            return
        if action == "draft_email":
            if not isinstance(args.get("to"), str) or "@" not in args.get("to", ""):
                raise ExecutionError("'to' must be an email string")
            if not isinstance(args.get("body"), str) or not args["body"].strip():
                raise ExecutionError("'body' must be provided for draft_email")
            return
        if action == "summarize_text":
            if not isinstance(args.get("text"), str) or not args["text"].strip():
                raise ExecutionError("'text' must be provided for summarize_text")
            return
        raise ExecutionError(f"Unknown openai action '{action}'")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        if action == "draft":
            return {"action": action, "draft": f"drafted: {args.get('prompt')}"}
        if action == "draft_email":
            return self.client.draft_email(
                to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", "")
            )
        if action == "summarize_text":
            return self.client.summarize_text(text=args.get("text", ""))
        raise ExecutionError(f"Unknown openai action '{action}'")
