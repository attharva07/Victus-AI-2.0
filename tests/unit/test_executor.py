import pytest
from datetime import datetime

from victus.core.executor import ExecutionEngine
from victus.core.policy import PolicyEngine
from victus.core.schemas import Context, Plan, PlanStep, PrivacySettings, ExecutionError
from victus.domains.system.system_plugin import SystemPlugin


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
    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(build_plan(), None)


def test_executor_requires_policy_signature():
    engine = ExecutionEngine({"system": SystemPlugin()})
    approval = PolicyEngine().evaluate(build_plan(), build_context())
    approval.policy_signature = ""
    with pytest.raises(ExecutionError):
        engine.execute(build_plan(), approval)


def test_executor_runs_approved_steps():
    plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(plan, context)
    engine = ExecutionEngine({"system": SystemPlugin()})
    results = engine.execute(plan, approval)
    assert "step-1" in results
    assert results["step-1"]["action"] == "open_app"


def test_executor_rejects_unapproved_step_id():
    plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(plan, context)
    approval.approved_steps = []
    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(plan, approval)


def test_executor_enforces_plugin_validation():
    bad_plan = Plan(
        goal="play music",
        domain="system",
        steps=[PlanStep(id="step-1", tool="system", action="open_app", args={"app": "unknown"})],
        risk="low",
    )
    context = build_context()
    approval = PolicyEngine().evaluate(bad_plan, context)
    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(bad_plan, approval)


def test_executor_rejects_mutated_approved_steps_signature():
    plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(plan, context)
    approval.approved_steps.append("step-2")
    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(plan, approval)


def test_executor_rejects_tampered_signature():
    plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(plan, context)
    approval.policy_signature = approval.policy_signature + "tamper"
    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(plan, approval)
