from __future__ import annotations

from typing import Sequence

from .schemas import Plan, PlanStep


class Planner:
    """Deterministic planner stub emitting a Plan from provided steps."""

    def build_plan(self, goal: str, domain: str, steps: Sequence[PlanStep], **kwargs) -> Plan:
        return Plan(goal=goal, domain=domain, steps=list(steps), **kwargs)
