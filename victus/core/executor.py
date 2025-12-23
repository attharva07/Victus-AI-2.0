from __future__ import annotations

from typing import Dict

from ..domains.base import BasePlugin
from .policy import compute_policy_signature
from .schemas import Approval, ExecutionError, Plan


class ExecutionEngine:
    def __init__(self, plugins: Dict[str, BasePlugin], signature_secret: str = "signed-policy") -> None:
        self.plugins = plugins
        self.signature_secret = signature_secret

    def execute(self, plan: Plan, approval: Approval) -> Dict[str, object]:
        if not approval or not approval.approved:
            raise ExecutionError("Execution refused: approval is missing or not approved")
        if not approval.policy_signature:
            raise ExecutionError("Execution refused: missing policy signature")

        expected_signature = compute_policy_signature(
            plan=plan,
            approved_steps=approval.approved_steps,
            constraints=approval.constraints,
            requires_confirmation=approval.requires_confirmation,
            secret=self.signature_secret,
        )
        if approval.policy_signature != expected_signature:
            raise ExecutionError("Execution refused: approval signature invalid or tampered")

        results = {}
        for step in plan.steps:
            if step.id not in approval.approved_steps:
                raise ExecutionError(f"Step {step.id} is not approved for execution")
            plugin = self._get_plugin(step.tool)
            plugin.validate_args(step.action, step.args)
            results[step.id] = plugin.execute(step.action, step.args, approval)
        return results

    def _get_plugin(self, name: str) -> BasePlugin:
        if name not in self.plugins:
            raise ExecutionError(f"No plugin registered for tool '{name}'")
        return self.plugins[name]
