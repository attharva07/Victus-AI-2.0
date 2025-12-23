import pytest
from datetime import datetime

from victus.core.policy import PolicyEngine
from victus.core.schemas import Context, Plan, PlanStep, PrivacySettings, StepIO, DataOutbound, PolicyError


@pytest.fixture
def base_context():
    return Context(
        session_id="123",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(),
    )


def _plan_with_step(step: PlanStep, **kwargs):
    defaults = dict(
        goal="test",
        domain="system",
        steps=[step],
        risk="low",
    )
    defaults.update(kwargs)
    return Plan(**defaults)


def test_unknown_tool_denied(base_context):
    plan = _plan_with_step(PlanStep(id="step-1", tool="unknown", action="do"))
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_denylisted_action_denied(base_context):
    plan = _plan_with_step(PlanStep(id="step-1", tool="system", action="raw_shell"))
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_system_action_not_allowlisted_denied(base_context):
    plan = _plan_with_step(PlanStep(id="step-1", tool="system", action="shutdown"))
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_productivity_tools_blocked_in_system_plans(base_context):
    plan = _plan_with_step(
        PlanStep(id="step-1", tool="gmail", action="send"),
        domain="system",
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_system_tools_blocked_in_productivity_plans(base_context):
    plan = _plan_with_step(
        PlanStep(id="step-1", tool="system", action="open_app"),
        domain="productivity",
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_mixed_domain_permits_both_tool_sets(base_context):
    plan = Plan(
        goal="multi",
        domain="mixed",
        steps=[
            PlanStep(id="step-1", tool="system", action="open_app", args={"app": "notes"}),
            PlanStep(id="step-2", tool="openai", action="draft", args={"prompt": "summarize"}),
        ],
        risk="low",
    )
    engine = PolicyEngine()
    context = Context(
        session_id=base_context.session_id,
        timestamp=base_context.timestamp,
        mode=base_context.mode,
        foreground_app=base_context.foreground_app,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    approval = engine.evaluate(plan, context)
    assert approval.approved is True


def test_mixed_plan_denied_when_privacy_blocks_screenshot_and_openai(base_context):
    plan = Plan(
        goal="sensitive mix",
        domain="mixed",
        steps=[
            PlanStep(
                id="step-1",
                tool="system",
                action="open_app",
                args={"app": "browser"},
                inputs=StepIO(uses_screenshot=True),
            ),
            PlanStep(id="step-2", tool="openai", action="draft", args={"prompt": "summarize"}),
        ],
        data_outbound=DataOutbound(to_openai=True),
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_mixed_plan_rejected_when_privacy_flags_false(base_context):
    plan = Plan(
        goal="openai without consent",
        domain="mixed",
        steps=[PlanStep(id="step-1", tool="openai", action="draft", args={"prompt": "summarize"})],
        data_outbound=DataOutbound(to_openai=True),
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_mixed_plan_denies_productivity_action_masquerading_as_system(base_context):
    plan = Plan(
        goal="misrouted action",
        domain="mixed",
        steps=[PlanStep(id="step-1", tool="docs", action="open_app", args={"app": "terminal"})],
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_productivity_plan_rejects_system_execution_attempt(base_context):
    plan = Plan(
        goal="productivity cannot execute system",
        domain="productivity",
        steps=[PlanStep(id="step-1", tool="system", action="net_snapshot", args={"detail": "summary"})],
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_gmail_send_requires_confirmation(base_context):
    plan = _plan_with_step(
        PlanStep(id="step-1", tool="gmail", action="send"),
        risk="low",
        domain="productivity",
    )
    engine = PolicyEngine()
    approval = engine.evaluate(plan, base_context)
    assert approval.requires_confirmation is True


def test_medium_risk_requires_confirmation(base_context):
    plan = _plan_with_step(PlanStep(id="step-1", tool="system", action="open_app"), risk="medium")
    engine = PolicyEngine()
    approval = engine.evaluate(plan, base_context)
    assert approval.requires_confirmation is True


def test_openai_data_denied_without_privacy_consent(base_context):
    outbound = DataOutbound(to_openai=True)
    plan = _plan_with_step(
        PlanStep(id="step-1", tool="openai", action="draft"),
        risk="low",
        domain="productivity",
        data_outbound=outbound,
    )
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_screenshot_requires_privacy_consent(base_context):
    step = PlanStep(id="step-1", tool="system", action="open_app", inputs=StepIO(uses_screenshot=True))
    plan = _plan_with_step(step)
    engine = PolicyEngine()
    with pytest.raises(PolicyError):
        engine.evaluate(plan, base_context)


def test_no_screenshot_storage_constraint_set_when_disabled(base_context):
    context = Context(
        session_id=base_context.session_id,
        timestamp=base_context.timestamp,
        mode=base_context.mode,
        foreground_app=base_context.foreground_app,
        privacy=PrivacySettings(allow_store_images=False),
    )
    plan = _plan_with_step(PlanStep(id="step-1", tool="system", action="open_app"))
    engine = PolicyEngine()
    approval = engine.evaluate(plan, context)
    assert approval.constraints.no_screenshot_store is True


def test_allows_openai_when_privacy_permits(base_context):
    context = Context(
        session_id=base_context.session_id,
        timestamp=base_context.timestamp,
        mode=base_context.mode,
        foreground_app=base_context.foreground_app,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    outbound = DataOutbound(to_openai=True)
    plan = _plan_with_step(
        PlanStep(id="step-1", tool="openai", action="draft"),
        risk="low",
        domain="productivity",
        data_outbound=outbound,
    )
    engine = PolicyEngine()
    approval = engine.evaluate(plan, context)
    assert approval.approved is True
