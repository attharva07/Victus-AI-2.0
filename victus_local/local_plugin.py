from __future__ import annotations

import asyncio
from typing import Any, Dict

from victus.core.schemas import Approval, ExecutionError
from victus.domains.base import BasePlugin

from .media_router import run_media_play, run_media_stop
from .task_runner import TaskError, run_task, validate_task_args


class LocalTaskPlugin(BasePlugin):
    """Local task executor that wraps allowlisted desktop actions."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "open_app": {"name": "Application name"},
            "open_youtube": {"query": "Search text or URL"},
            "media_play": {"provider": "spotify|youtube", "query": "Search text", "artist": "Optional"},
            "media_stop": {"provider": "spotify|youtube"},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action in {"media_play", "media_stop"}:
            if action == "media_play":
                provider = (args.get("provider") or "").strip().lower()
                if provider and provider not in {"spotify", "youtube"}:
                    raise ExecutionError("media_play provider must be spotify or youtube")
            elif action == "media_stop":
                provider = (args.get("provider") or "").strip().lower()
                if provider and provider not in {"spotify", "youtube"}:
                    raise ExecutionError("media_stop provider must be spotify or youtube")
            return

        try:
            validate_task_args(action, args)
        except TaskError as exc:
            raise ExecutionError(str(exc)) from exc

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        if action == "media_play":
            return run_media_play(args)
        if action == "media_stop":
            provider = (args.get("provider") or "spotify").strip().lower()
            return run_media_stop(provider)
        try:
            return asyncio.run(run_task(action, args))
        except TaskError as exc:
            return {"error": str(exc)}
