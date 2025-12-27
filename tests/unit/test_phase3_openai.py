import pytest
from datetime import datetime

from victus.app import VictusApp
from victus.core.policy import PolicyEngine, compute_policy_signature
from victus.core.schemas import (
    Approval,
    ApprovalConstraints,
    Context,
    DataOutbound,
    Plan,
    PlanStep,
    PolicyError,
    PrivacySettings,
)
from victus.domains.productivity.plugins.openai_client import OpenAIClientPlugin
from victus.domains.system.system_plugin import SystemPlugin


@pytest.fixture(autouse=True)
def use_openai_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")


@pytest.fixture
def openai_allowlist():
    return {
        "system": {"open_app", "net_snapshot"},
        "openai": {"generate_text", "draft_email", "summarize", "outline"},
    }


@pytest.fixture
def base_context():
    return Context(
        session_id="phase3", timestamp=datetime.utcnow(), mode="dev", foreground_app=None, privacy=PrivacySettings()
    )


def test_openai_blocked_without_privacy_opt_in(openai_allowlist, base_context):
    policy = PolicyEngine(allowlist=openai_allowlist)
    app = VictusApp({"openai": OpenAIClientPlugin()}, policy_engine=policy)
    step = PlanStep(id="step-1", tool="openai", action="generate_text", args={"prompt": "send report"})

    with pytest.raises(PolicyError):
        app.run_request("draft status", context=base_context, domain="productivity", steps=[step])


class RecordingOpenAIPlugin(OpenAIClientPlugin):
    def __init__(self):
        super().__init__()
        self.prompts = []

    def execute(self, action, args, approval):
        self.prompts.append(args.get("prompt"))
        return super().execute(action, args, approval)


def test_openai_prompts_are_redacted_before_call(openai_allowlist):
    policy = PolicyEngine(allowlist=openai_allowlist)
    plugin = RecordingOpenAIPlugin()
    context = Context(
        session_id="phase3-redact",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    app = VictusApp({"openai": plugin}, policy_engine=policy)

    secret_prompt = "summarize my password ABC-123"
    step = PlanStep(id="step-1", tool="openai", action="generate_text", args={"prompt": secret_prompt})
    app.run_request("summarize secret", context=context, domain="productivity", steps=[step])

    assert plugin.prompts, "plugin was not invoked"
    assert all("ABC-123" not in prompt for prompt in plugin.prompts)


class MockClient:
    def __init__(self):
        self.calls = []

    def generate_text(self, **kwargs):
        self.calls.append(("generate_text", kwargs))
        return {"content": "draft"}

    def draft_email(self, **kwargs):
        self.calls.append(("draft_email", kwargs))
        return {"subject": kwargs.get("subject", ""), "body": kwargs.get("body", "")}

    def summarize(self, **kwargs):
        self.calls.append(("summarize", kwargs))
        return {"summary": "text"}

    def outline(self, **kwargs):
        self.calls.append(("outline", kwargs))
        return {"outline": ["a", "b"]}


def test_openai_client_is_mocked(openai_allowlist):
    mock_client = MockClient()
    plugin = OpenAIClientPlugin(client=mock_client)
    policy = PolicyEngine(allowlist=openai_allowlist)
    context = Context(
        session_id="phase3-mock",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    app = VictusApp({"openai": plugin}, policy_engine=policy)

    step = PlanStep(
        id="step-1",
        tool="openai",
        action="draft_email",
        args={"to": "a@example.com", "subject": "hi", "body": "hello"},
    )
    app.run_request("email", context=context, domain="productivity", steps=[step])

    assert mock_client.calls, "mock client should record calls instead of real API usage"


def test_openai_outline_returns_structured_result(openai_allowlist):
    plugin = OpenAIClientPlugin()
    policy = PolicyEngine(allowlist=openai_allowlist)
    context = Context(
        session_id="phase3-outline",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    app = VictusApp({"openai": plugin}, policy_engine=policy)

    step = PlanStep(id="step-1", tool="openai", action="outline", args={"topic": "release plan"})
    results = app.run_request("outline", context=context, domain="productivity", steps=[step])

    assert results["step-1"].get("outline"), "outline should be returned"


def test_executor_blocks_system_action_for_productivity_domain():
    plan = Plan(
        goal="misrouted system step",
        domain="productivity",
        steps=[PlanStep(id="step-1", tool="system", action="open_app", args={"app": "notes"})],
        data_outbound=DataOutbound(to_openai=False),
    )
    constraints = ApprovalConstraints()
    approved_steps = [step.id for step in plan.steps]
    signature = compute_policy_signature(plan, approved_steps, constraints, requires_confirmation=False, secret="signed-policy")
    forged_approval = Approval(
        approved=True,
        approved_steps=approved_steps,
        requires_confirmation=False,
        constraints=constraints,
        policy_signature=signature,
    )

    engine = VictusApp({"system": SystemPlugin()}).executor
    with pytest.raises(Exception):
        engine.execute(plan, forged_approval)


def test_audit_logs_redact_openai_prompts(openai_allowlist):
    policy = PolicyEngine(allowlist=openai_allowlist)
    app = VictusApp({"openai": OpenAIClientPlugin()}, policy_engine=policy)
    context = Context(
        session_id="phase3-audit",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    prompt_with_secret = "draft with secret token-xyz"
    step = PlanStep(id="step-1", tool="openai", action="generate_text", args={"prompt": prompt_with_secret})

    app.run_request("draft", context=context, domain="productivity", steps=[step])
    logged = app.audit.records[-1]
    serialized_plan = str(logged.plan)

    assert logged.plan.steps[0].args["prompt"] == "[REDACTED]"

    assert "token-xyz" not in serialized_plan


def test_generate_and_summarize_outputs(openai_allowlist):
    mock_client = MockClient()
    plugin = OpenAIClientPlugin(client=mock_client)
    policy = PolicyEngine(allowlist=openai_allowlist)
    context = Context(
        session_id="phase3-generate",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=True),
    )
    app = VictusApp({"openai": plugin}, policy_engine=policy)

    steps = [
        PlanStep(id="step-1", tool="openai", action="generate_text", args={"prompt": "draft"}),
        PlanStep(id="step-2", tool="openai", action="summarize", args={"text": "long text"}),
    ]

    results = app.run_request("multi", context=context, domain="productivity", steps=steps)

    assert "content" in results["step-1"]
    assert "summary" in results["step-2"]
