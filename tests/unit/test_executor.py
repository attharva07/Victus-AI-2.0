import pytest
from datetime import datetime

from victus.app import VictusApp
from victus.core.executor import ExecutionEngine
from victus.core.policy import PolicyEngine, compute_policy_signature
from victus.core.schemas import (
    Context,
    DataOutbound,
    ExecutionError,
    Plan,
    PlanStep,
    PrivacySettings,
)
from victus.domains.productivity.plugins.openai_client import OpenAIClientPlugin

from victus.domains.system.system_plugin import SystemPlugin


@pytest.fixture(autouse=True)
def use_openai_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")


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


def build_openai_plan():
    return Plan(
        goal="draft",
        domain="productivity",
        steps=[
            PlanStep(
                id="step-1",
                tool="openai",
                action="generate_text",
                args={"prompt": "secret", "to": "user@example.com"},
            )
        ],
        data_outbound=DataOutbound(to_openai=True),
    )


def build_openai_context():
    return Context(
        session_id="openai-session",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
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


def test_executor_rejects_approval_reused_for_different_plan():
    original_plan = build_plan()
    context = build_context()
    approval = PolicyEngine().evaluate(original_plan, context)

    mutated_plan = Plan(
        goal="play music differently",
        domain="system",
        steps=[PlanStep(id="step-2", tool="system", action="open_app", args={"app": "notes"})],
        risk="low",
    )

    engine = ExecutionEngine({"system": SystemPlugin()})
    with pytest.raises(ExecutionError):
        engine.execute(mutated_plan, approval)


def test_policy_signature_uses_redacted_payload():
    app = VictusApp(plugins={})
    raw_plan = build_openai_plan()
    context = build_openai_context()

    prepared_plan, approval = app.request_approval(raw_plan, context)

    redacted_args = prepared_plan.steps[0].args
    assert redacted_args["prompt"] == "[REDACTED]"
    assert redacted_args["to"] == "redacted@example.com"

    expected_signature = compute_policy_signature(
        plan=prepared_plan,
        approved_steps=approval.approved_steps,
        constraints=approval.constraints,
        requires_confirmation=approval.requires_confirmation,
        secret=app.policy_engine.signature_secret,
    )

    assert approval.policy_signature == expected_signature


def test_executor_rejects_raw_payload_after_redacted_approval():
    app = VictusApp(plugins={})
    raw_plan = build_openai_plan()
    context = build_openai_context()

    _, approval = app.request_approval(raw_plan, context)

    with pytest.raises(ExecutionError):
        app.executor.execute(raw_plan, approval)


class RecordingOpenAIPlugin(OpenAIClientPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.seen_args = []

    def execute(self, action, args, approval):
        self.seen_args.append(args)
        return super().execute(action, args, approval)


def test_executor_only_runs_sanitized_plan_payload():
    plugin = RecordingOpenAIPlugin()
    app = VictusApp(plugins={"openai": plugin})
    raw_plan = build_openai_plan()
    context = build_openai_context()

    sanitized_plan, approval = app.request_approval(raw_plan, context)
    app.executor.execute(sanitized_plan, approval)

    assert plugin.seen_args, "plugin should capture executed args"
    assert all("secret" not in str(args.get("prompt", "")) for args in plugin.seen_args)


def test_audit_always_stores_sanitized_plan():
    app = VictusApp(plugins={})
    raw_plan = build_openai_plan()
    context = build_openai_context()
    _, approval = app.request_approval(raw_plan, context)

    record = app.audit.log_request(
        user_input="test",
        plan=raw_plan,
        approval=approval,
        results={"step-1": {"status": "ok"}},
        errors=None,
    )

    logged_args = record.plan.steps[0].args
    assert logged_args["prompt"] == "[REDACTED]"
    assert logged_args["to"] == "redacted@example.com"
    assert "secret" not in str(record.plan)

