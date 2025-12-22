from datetime import datetime

import pytest

from victus.executor import ExecutionEngine
from victus.plugins.base import DummyPlugin
from victus.policy import PolicyEngine
from victus.schemas import Context, Plan, PlanStep, PrivacySettings, ExecutionError


def build_plan():
    return Plan(
        goal="play music",
        domain="system",
        steps=[PlanStep(id="step-1", tool="system", action="open_app", args={"app": "spotify"})],
        risk="low",
    )


def build_context(allow_screenshot=True):
    return Context(
        session_id="abc",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_screenshot=allow_screenshot),
    )


def test_executor_refuses_without_approval():
    engine = ExecutionEngine({"system": DummyPlugin({"open_app"})})
    with pytest.raises(ExecutionError):
        engine.execute(build_plan(), None)


def test_executor_requires_policy_signature():
    engine = ExecutionEngine({"system": DummyPlugin({"open_app"})})
    approval = PolicyEngine().evaluate(build_plan(), build_context())
    approval.policy_signature = ""
    with pytest.raises(ExecutionError):
        engine.execute(build_plan(), approval)


def test_executor_runs_approved_steps():
    plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(plan, context)
    engine = ExecutionEngine({"system": DummyPlugin({"open_app"})})
    results = engine.execute(plan, approval)
    assert "step-1" in results
    assert results["step-1"]["action"] == "open_app"
