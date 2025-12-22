from datetime import datetime

from victus.core.audit import AuditLogger
from victus.core.schemas import Approval, ApprovalConstraints, Context, Plan, PlanStep, PrivacySettings


def build_context():
    return Context(
        session_id="log-1",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(),
    )


def build_plan():
    return Plan(
        goal="log",
        domain="system",
        steps=[PlanStep(id="step-1", tool="system", action="open_app")],
        risk="low",
    )


def build_approval():
    return Approval(
        approved=True,
        approved_steps=["step-1"],
        requires_confirmation=False,
        constraints=ApprovalConstraints(),
        policy_signature="signed-policy",
    )


def test_audit_records_and_redacts_secrets():
    logger = AuditLogger()
    record = logger.log_request(
        user_input="do something",
        plan=build_plan(),
        approval=build_approval(),
        results={"step-1": "ok"},
        errors=None,
        secrets=["token123"],
    )
    assert record in logger.records
    assert record.redacted_secrets == ["[REDACTED]"]


def test_audit_captures_errors():
    logger = AuditLogger()
    error_text = "policy failed"
    record = logger.log_request(
        user_input="fail",
        plan=build_plan(),
        approval=None,
        results=None,
        errors=error_text,
    )
    assert record.errors == error_text
