from __future__ import annotations

from dataclasses import replace
from typing import Any

from .schemas import Plan


def sanitize_plan(plan: Plan) -> Plan:
    """Return a copy of the plan with outbound flows marked and OpenAI args redacted."""

    outbound_marked = _mark_openai_outbound(plan)
    return _redact_openai_steps(outbound_marked)


def _mark_openai_outbound(plan: Plan) -> Plan:
    if not any(step.tool == "openai" for step in plan.steps):
        return plan

    outbound = replace(plan.data_outbound, to_openai=True)
    return replace(plan, data_outbound=outbound)


def _redact_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if key == "to":
        return "redacted@example.com"
    return "[REDACTED]"


def _redact_openai_steps(plan: Plan) -> Plan:
    if not plan.data_outbound.redaction_required:
        return plan

    redacted_steps = []
    for step in plan.steps:
        if step.tool != "openai":
            redacted_steps.append(step)
            continue

        redacted_args = {key: _redact_value(key, value) for key, value in step.args.items()}
        redacted_steps.append(replace(step, args=redacted_args))

    return replace(plan, steps=redacted_steps)
