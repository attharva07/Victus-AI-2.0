from __future__ import annotations

from typing import Any, Dict

from ..base import BasePlugin
from ...core.schemas import Approval, ExecutionError
from .plugins.openai_client import OpenAIClientPlugin


class GmailPlugin(BasePlugin):
    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"send": {"to": "email", "subject": "text", "body": "text"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "send":
            raise ExecutionError("Unknown gmail action requested")
        if not isinstance(args.get("to"), str) or "@" not in args["to"]:
            raise ExecutionError("gmail.send requires a recipient email")
        if not isinstance(args.get("subject"), str) or not isinstance(args.get("body"), str):
            raise ExecutionError("gmail.send requires text subject and body")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"action": action, "sent": args.get("to"), "subject": args.get("subject")}


class SpotifyPlugin(BasePlugin):
    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"play": {"track": "text"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "play":
            raise ExecutionError("Unknown spotify action requested")
        if not isinstance(args.get("track"), str) or not args["track"].strip():
            raise ExecutionError("spotify.play requires a track string")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"action": action, "playing": args.get("track")}


class DocsPlugin(BasePlugin):
    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {"create": {"title": "text", "content": "text"}}

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action != "create":
            raise ExecutionError("Unknown docs action requested")
        if not isinstance(args.get("title"), str) or not args["title"].strip():
            raise ExecutionError("docs.create requires a title")
        if not isinstance(args.get("content"), str):
            raise ExecutionError("docs.create requires content text")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        return {"action": action, "doc_id": f"doc-{args.get('title')}"}


class OpenAIPlugin(OpenAIClientPlugin):
    """Backward-compatible alias for the OpenAI client plugin."""
