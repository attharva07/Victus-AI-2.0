from __future__ import annotations

"""Victus Phase 1 application scaffold.

This module wires together the router, planner, policy engine, executor, and
audit logger. It demonstrates the enforced flow: Input -> Plan -> Policy ->
Approval -> Execute -> Audit. Real interfaces (UI/voice/hotkey) will call into
`VictusApp.run_request` in later phases.
"""

from typing import Dict, Sequence

from .core.approval import issue_approval
from .core.audit import AuditLogger
from .core.executor import ExecutionEngine
from .core.planner import Planner
from .core.policy import PolicyEngine
from .core.router import Router
from .core.schemas import Approval, Context, Plan, PlanStep
from .domains.base import BasePlugin


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

    def request_approval(self, plan: Plan, context: Context) -> Approval:
        """Issue a policy approval for the provided plan/context."""

        return issue_approval(plan, context, self.policy_engine)

    def execute_plan(self, plan: Plan, approval: Approval) -> Dict[str, object]:
        """Execute an approved plan via the execution engine."""

        return self.executor.execute(plan, approval)

    def run_request(self, user_input: str, context: Context, domain: str, steps: Sequence[PlanStep]) -> Dict[str, object]:
        """Run the full request lifecycle and record an audit entry.

        Exceptions propagate after being logged so callers can handle errors.
        """

        routed = self.router.route(user_input, context)
        plan = self.build_plan(goal=user_input, domain=domain, steps=steps)
        approval = self.request_approval(plan, routed.context)
        results = self.execute_plan(plan, approval)
        self.audit.log_request(
            user_input=user_input,
            plan=plan,
            approval=approval,
            results=results,
            errors=None,
        )
        return results
