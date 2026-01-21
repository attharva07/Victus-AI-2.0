from __future__ import annotations

import sys
from typing import Any, Callable, Dict, List, Optional

from ...base import BasePlugin
from ....config.runtime import (
    get_llm_provider,
    get_ollama_base_url,
    get_ollama_model,
    is_openai_configured,
)
from ....core.llm_health import get_llm_circuit_breaker
from ....core.schemas import Approval, ExecutionError
from .llm_base import LLMClientBase

LIMITED_MODE_MESSAGE = "LLM is unavailable (limited mode). Try a direct command (e.g., 'open calculator')."


class OpenAIClientStub(LLMClientBase):
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

    def __init__(self, client: Optional[LLMClientBase] = None) -> None:
        if client is not None:
            self.client = client
            return

        if self._running_tests():
            self.client = OpenAIClientStub()
            return

        provider = get_llm_provider()
        if provider == "ollama":
            from .ollama_client import OllamaClient

            self.client = OllamaClient(
                base_url=get_ollama_base_url(),
                model=get_ollama_model(),
            )
        elif provider == "openai":
            if not is_openai_configured():
                raise ExecutionError(
                    "OPENAI_API_KEY is required when LLM provider is set to 'openai'."
                )
            from .openai_real_client import OpenAIClientReal

            self.client = OpenAIClientReal()
        else:
            raise ExecutionError(f"Unsupported LLM provider '{provider}'.")

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "generate_text": {"description": "Draft text using an LLM provider"},
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

        breaker = get_llm_circuit_breaker()
        if not breaker.allow_request():
            return {"assistant_message": LIMITED_MODE_MESSAGE}

        if action in {"draft", "generate_text"}:
            return self._call_with_breaker(self.client.generate_text, breaker, prompt=args.get("prompt", ""))
        if action == "draft_email":
            return self._call_with_breaker(
                self.client.draft_email,
                breaker,
                to=args.get("to", ""),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
            )
        if action in {"summarize", "summarize_text"}:
            return self._call_with_breaker(self.client.summarize, breaker, text=args.get("text", ""))
        if action == "outline":
            return self._call_with_breaker(self.client.outline, breaker, topic=args.get("topic", ""))
        raise ExecutionError(f"Unknown openai action '{action}'")

    def stream_execute(
        self,
        action: str,
        args: Dict[str, Any],
        approval: Approval,
        *,
        on_chunk: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> Any:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")

        breaker = get_llm_circuit_breaker()
        if not breaker.allow_request():
            return {"assistant_message": LIMITED_MODE_MESSAGE}

        if action in {"draft", "generate_text"}:
            stream_fn = getattr(self.client, "stream_generate_text", None)
            try:
                if callable(stream_fn):
                    content = stream_fn(
                        prompt=args.get("prompt", ""),
                        on_chunk=on_chunk,
                        should_stop=should_stop,
                    )
                else:
                    content = self.client.generate_text(prompt=args.get("prompt", ""))["content"]
                    if on_chunk:
                        chunk_size = 48
                        for idx in range(0, len(content), chunk_size):
                            if should_stop and should_stop():
                                break
                            on_chunk(content[idx : idx + chunk_size])
            except Exception as exc:  # noqa: BLE001
                breaker.record_failure(exc)
                raise
            breaker.record_success()
            return {"action": "generate_text", "content": content}

        return self.execute(action, args, approval)

    @staticmethod
    def _call_with_breaker(func: Callable[..., Any], breaker, **kwargs: Any) -> Any:
        try:
            result = func(**kwargs)
        except Exception as exc:  # noqa: BLE001
            breaker.record_failure(exc)
            raise
        breaker.record_success()
        return result

    @staticmethod
    def _running_tests() -> bool:
        return "pytest" in sys.modules


LLMClientPlugin = OpenAIClientPlugin
