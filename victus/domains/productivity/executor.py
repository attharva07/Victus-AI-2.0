from __future__ import annotations

from typing import Dict

from ..base import BasePlugin
from ...core.schemas import Approval, Plan, ExecutionError


class ProductivityExecutor:
    """Productivity executor placeholder for Phase 1."""

    def __init__(self, plugins: Dict[str, BasePlugin]):
        self.plugins = plugins

    def execute(self, plan: Plan, approval: Approval):
        if not approval.policy_signature:
            raise ExecutionError("Execution refused: missing policy signature")
        results = {}
        for step in plan.steps:
            plugin = self._get_plugin(step.action)
            plugin.validate_args(step.action, step.args)
            results[step.id] = plugin.execute(step.action, step.args, approval)
        return results

    def _get_plugin(self, action: str) -> BasePlugin:
        if action not in self.plugins:
            raise ExecutionError(f"No plugin registered for productivity action '{action}'")
        return self.plugins[action]
