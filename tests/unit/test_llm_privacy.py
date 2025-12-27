import pytest
from datetime import datetime

from victus.core.policy import PolicyEngine, PolicyError
from victus.core.sanitization import sanitize_plan
from victus.core.schemas import Context, Plan, PlanStep, PrivacySettings


def build_llm_plan(prompt: str) -> Plan:
    return Plan(
        goal="llm task",
        domain="productivity",
        steps=[PlanStep(id="step-1", tool="openai", action="generate_text", args={"prompt": prompt})],
        risk="low",
    )


def build_context(allow_send: bool = False) -> Context:
    return Context(
        session_id="llm-session",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_send_to_openai=allow_send),
    )


def test_ollama_provider_bypasses_redaction(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    plan = build_llm_plan("local secret")

    sanitized = sanitize_plan(plan)

    assert sanitized.steps[0].args["prompt"] == "local secret"
    assert sanitized.data_outbound.to_openai is False
    assert sanitized.data_outbound.redaction_required is False


def test_outbound_provider_redacts_and_requires_opt_in(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    plan = build_llm_plan("sensitive prompt")

    sanitized = sanitize_plan(plan)

    assert sanitized.steps[0].args["prompt"] == "[REDACTED]"

    with pytest.raises(PolicyError):
        PolicyEngine().evaluate(sanitized, build_context())
