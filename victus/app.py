from __future__ import annotations

"""Victus Phase 1 application scaffold.

This module wires together the router, planner, policy engine, executor, and
audit logger. It demonstrates the enforced flow: Input -> Plan -> Policy ->
Approval -> Execute -> Audit. Real interfaces (UI/voice/hotkey) will call into
`VictusApp.run_request` in later phases.
"""

from dataclasses import replace
from typing import Dict, Sequence

from .core.approval import issue_approval
from .core.audit import AuditLogger
from .core.executor import ExecutionEngine
from .core.planner import Planner
from .core.policy import PolicyEngine
from .core.router import Router
from .core.sanitization import sanitize_plan
from .core.schemas import Approval, Context, Plan, PlanStep
from .domains.base import BasePlugin
from .config.runtime import get_llm_provider, is_outbound_llm_provider


class VictusApp:
    def __init__(
        self,
        plugins: Dict[str, BasePlugin],
        policy_engine: PolicyEngine | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.router = Router()
        self.planner = Planner()
        self.policy_engine = policy_engine or PolicyEngine()
        self.executor = ExecutionEngine(plugins, signature_secret=self.policy_engine.signature_secret)
        self.audit = audit_logger or AuditLogger()

    def build_plan(self, goal: str, domain: str, steps: Sequence[PlanStep], **kwargs) -> Plan:
        """Create a plan using the deterministic planner stub."""

        return self.planner.build_plan(goal=goal, domain=domain, steps=steps, **kwargs)

    def prepare_plan_for_policy(self, plan: Plan) -> Plan:
        """Mark outbound flows and redact sensitive arguments before policy review."""

        return sanitize_plan(plan)

    def request_approval(self, plan: Plan, context: Context) -> tuple[Plan, Approval]:
        """Prepare and submit a plan for approval, returning the redacted copy."""

        prepared_plan = self.prepare_plan_for_policy(plan)
        approval = issue_approval(prepared_plan, context, self.policy_engine)
        return prepared_plan, approval

    def execute_plan(self, plan: Plan, approval: Approval) -> Dict[str, object]:
        """Execute an approved plan via the execution engine."""

        return self.executor.execute(plan, approval)

    def run_request(self, user_input: str, context: Context, domain: str, steps: Sequence[PlanStep]) -> Dict[str, object]:
        """Run the full request lifecycle and record an audit entry.

        Exceptions propagate after being logged so callers can handle errors.
        """

        routed = self.router.route(user_input, context)
        plan = self.build_plan(goal=user_input, domain=domain, steps=steps)
        prepared_plan, approval = self.request_approval(plan, routed.context)
        results = self.execute_plan(prepared_plan, approval)
        self.audit.log_request(
            user_input=user_input,
            plan=prepared_plan,
            approval=approval,
            results=results,
            errors=None,
        )
        return results

    @staticmethod
    def _mark_openai_outbound(plan: Plan) -> Plan:
        provider = get_llm_provider()
        is_outbound = is_outbound_llm_provider(provider)
        outbound = replace(
            plan.data_outbound,
            to_openai=is_outbound and any(step.tool == "openai" for step in plan.steps),
            redaction_required=is_outbound and plan.data_outbound.redaction_required,
        )
        return replace(plan, data_outbound=outbound)

    @staticmethod
    def _redact_value(key: str, value: object) -> object:
        if not isinstance(value, str):
            return value
        if key == "to":
            return "redacted@example.com"
        return "[REDACTED]"

    def _redact_openai_steps(self, plan: Plan) -> Plan:
        if not plan.data_outbound.redaction_required:
            return plan

        redacted_steps = []
        for step in plan.steps:
            if step.tool != "openai":
                redacted_steps.append(step)
                continue
            redacted_args = {key: self._redact_value(key, value) for key, value in step.args.items()}
            redacted_steps.append(replace(step, args=redacted_args))

        return replace(plan, steps=redacted_steps)
