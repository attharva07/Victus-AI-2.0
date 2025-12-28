from __future__ import annotations

from typing import Callable, Dict, Optional

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
            if plan.domain == "productivity" and step.tool == "system":
                raise ExecutionError("Productivity domain cannot execute system actions")
            if plan.domain == "system" and getattr(plan, "origin", "planner") != "router":
                raise ExecutionError("System plans must originate from the deterministic router")
            if plan.domain == "system" and step.tool != "system":
                raise ExecutionError("System domain cannot execute non-system actions")
            plugin = self._get_plugin(step.tool)
            plugin.validate_args(step.action, step.args)
            results[step.id] = plugin.execute(step.action, step.args, approval)
        return results

    def execute_streaming(
        self,
        plan: Plan,
        approval: Approval,
        *,
        stream_callbacks: Optional[Dict[str, Callable[[str], None]]] = None,
        stop_requests: Optional[Dict[str, Callable[[], bool]]] = None,
    ) -> Dict[str, object]:
        """Execute a plan while optionally streaming step outputs.

        If a callback is supplied for a step ID, the corresponding plugin's
        ``stream_execute`` method is used; otherwise ``execute`` is invoked.
        """

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
        callbacks = stream_callbacks or {}
        stop_map = stop_requests or {}
        for step in plan.steps:
            if step.id not in approval.approved_steps:
                raise ExecutionError(f"Step {step.id} is not approved for execution")
            if plan.domain == "productivity" and step.tool == "system":
                raise ExecutionError("Productivity domain cannot execute system actions")
            if plan.domain == "system" and getattr(plan, "origin", "planner") != "router":
                raise ExecutionError("System plans must originate from the deterministic router")
            if plan.domain == "system" and step.tool != "system":
                raise ExecutionError("System domain cannot execute non-system actions")
            plugin = self._get_plugin(step.tool)
            plugin.validate_args(step.action, step.args)
            callback = callbacks.get(step.id)
            stop_request = stop_map.get(step.id)
            if callback is not None or stop_request is not None:
                results[step.id] = plugin.stream_execute(
                    step.action,
                    step.args,
                    approval,
                    on_chunk=callback,
                    should_stop=stop_request,
                )
                continue
            results[step.id] = plugin.execute(step.action, step.args, approval)
        return results

    def _get_plugin(self, name: str) -> BasePlugin:
        if name not in self.plugins:
            raise ExecutionError(f"No plugin registered for tool '{name}'")
        return self.plugins[name]
