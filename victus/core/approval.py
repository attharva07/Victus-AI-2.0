from __future__ import annotations

from .policy import PolicyEngine
from .schemas import Approval, Context, Plan


def issue_approval(plan: Plan, context: Context, engine: PolicyEngine) -> Approval:
    """Request an approval token from the policy engine."""

    return engine.evaluate(plan, context)
