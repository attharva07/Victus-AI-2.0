from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ...base import BasePlugin
from ....core.schemas import Approval, ExecutionError


class OpenAIClientStub:
    def generate_text(self, *, prompt: str) -> Dict[str, str]:
        return {"action": "generate_text", "content": f"draft: {prompt}"}

    def draft_email(self, *, to: str, subject: str, body: str) -> Dict[str, str]:
        return {"action": "draft_email", "to": to, "subject": subject, "body": body}

    def summarize(self, *, text: str) -> Dict[str, str]:
        return {"action": "summarize", "summary": text[:200] if text else ""}

    def outline(self, *, topic: str) -> Dict[str, List[str]]:
        return {"action": "outline", "outline": [topic] if topic else []}


class OpenAIClientPlugin(BasePlugin):
    """Stub OpenAI client that drafts or summarizes text when approved."""

    def __init__(self, client: Optional[Any] = None) -> None:
        if client is not None:
            self.client = client
            return

        if os.getenv("OPENAI_API_KEY"):
            from .openai_real_client import OpenAIClientReal

            self.client = OpenAIClientReal()
        else:
            self.client = OpenAIClientStub()

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "generate_text": {"description": "Draft text using OpenAI"},
            "draft_email": {"description": "Draft an email body"},
            "summarize": {"description": "Summarize provided text"},
            "outline": {"description": "Create a structured outline"},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action in {"draft", "generate_text"}:
            if not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
                raise ExecutionError("'prompt' argument is required")
            return
        if action == "draft_email":
            if not isinstance(args.get("subject"), str) or not args["subject"].strip():
                raise ExecutionError("'subject' must be provided for draft_email")
            if not isinstance(args.get("body"), str) or not args["body"].strip():
                raise ExecutionError("'body' must be provided for draft_email")
            if "to" in args and (not isinstance(args.get("to"), str) or "@" not in args.get("to", "")):
                raise ExecutionError("'to' must be an email string")
            return
        if action in {"summarize", "summarize_text"}:
            if not isinstance(args.get("text"), str) or not args["text"].strip():
                raise ExecutionError("'text' must be provided for summarize")
            return
        if action == "outline":
            if not isinstance(args.get("topic"), str) or not args["topic"].strip():
                raise ExecutionError("'topic' must be provided for outline")
            return
        raise ExecutionError(f"Unknown openai action '{action}'")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")

        if action in {"draft", "generate_text"}:
            return self.client.generate_text(prompt=args.get("prompt", ""))
        if action == "draft_email":
            return self.client.draft_email(
                to=args.get("to", ""), subject=args.get("subject", ""), body=args.get("body", "")
            )
        if action in {"summarize", "summarize_text"}:
            return self.client.summarize(text=args.get("text", ""))
        if action == "outline":
            return self.client.outline(topic=args.get("topic", ""))
        raise ExecutionError(f"Unknown openai action '{action}'")
