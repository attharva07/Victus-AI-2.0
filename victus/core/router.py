from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .intent_router import route_intent
from .safety_filter import SafetyFilter
from .schemas import Context, Plan, PlanStep


@dataclass
class RoutedRequest:
    user_input: str
    context: Context
    plan: Optional[Plan]


class Router:
    """Simple request router placeholder.

    Phase 1 only validates that an input/context pair is packaged for planning.
    """

    def __init__(self) -> None:
        self.safety_filter = SafetyFilter()

    def route(self, user_input: str, context: Context) -> RoutedRequest:
        if not user_input:
            raise ValueError("user_input must be provided")
        inferred_plan = self._map_intent_to_plan(user_input)
        return RoutedRequest(user_input=user_input, context=context, plan=inferred_plan)

    def _map_intent_to_plan(self, user_input: str) -> Plan | None:
        routed = route_intent(user_input, safety_filter=self.safety_filter)
        if not routed:
            return None

        step = PlanStep(id="step-1", tool="system", action=routed.action, args=routed.args)
        return Plan(goal=user_input, domain="system", steps=[step], risk="low", origin="router")
