from __future__ import annotations

import asyncio
from typing import Any, Dict

from victus.core.schemas import Approval, ExecutionError
from victus.domains.base import BasePlugin

from .task_runner import TaskError, run_task, validate_task_args


class LocalTaskPlugin(BasePlugin):
    """Local task executor that wraps allowlisted desktop actions."""

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "open_app": {"name": "Application name or path"},
            "open_youtube": {"query": "Search text or URL"},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        try:
            validate_task_args(action, args)
        except TaskError as exc:
            raise ExecutionError(str(exc)) from exc

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        try:
            return asyncio.run(run_task(action, args))
        except TaskError as exc:
            return {"error": str(exc)}
