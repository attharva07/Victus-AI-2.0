from datetime import datetime

from victus.app import VictusApp
from victus.core.schemas import Context, PlanStep, PrivacySettings
from victus.domains.system.system_plugin import SystemPlugin
from victus.domains.productivity.allowlisted_plugins import GmailPlugin, DocsPlugin


def build_context():
    return Context(
        session_id="session-1",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_screenshot=True, allow_send_to_openai=True),
    )


def test_app_runs_full_phase_one_flow():
    app = VictusApp({"system": SystemPlugin()})
    step = PlanStep(id="step-1", tool="system", action="open_app", args={"app": "spotify"})

    results = app.run_request(
        user_input="open spotify",
        context=build_context(),
        domain="system",
        steps=[step],
    )

    assert results["step-1"]["action"] == "open_app"
    assert app.audit.records[-1].approval.approved is True


def test_app_runs_mixed_phase_two_flow():
    plugins = {
        "system": SystemPlugin(),
        "gmail": GmailPlugin(),
        "docs": DocsPlugin(),
    }
    app = VictusApp(plugins)
    steps = [
        PlanStep(id="step-1", tool="system", action="open_app", args={"app": "notes"}),
        PlanStep(
            id="step-2",
            tool="docs",
            action="create",
            args={"title": "Phase 2", "content": "finished"},
        ),
    ]

    results = app.run_request(
        user_input="summarize phase 2 and share",
        context=build_context(),
        domain="mixed",
        steps=steps,
    )

    assert results["step-1"]["opened"] == "notes"
    assert results["step-2"]["doc_id"].startswith("doc-Phase 2")
    audit_record = app.audit.records[-1]
    assert audit_record.approval.requires_confirmation is False
