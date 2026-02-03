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
    results = app.run_request_sync(
        user_input="system status",
        context=build_context(),
        domain="system",
        steps=[],
    )

    assert results["step-1"]["action"] == "status"
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

    results = app.run_request_sync(
        user_input="summarize phase 2 and share",
        context=build_context(),
        domain="mixed",
        steps=steps,
    )

    assert results["step-1"]["opened"] == "notes"
    assert results["step-2"]["doc_id"].startswith("doc-Phase 2")
    audit_record = app.audit.records[-1]
    assert audit_record.approval.requires_confirmation is False


def test_system_intent_router_skips_planner(monkeypatch):
    app = VictusApp({"system": SystemPlugin()})
    planner_called = False

    original_build_plan = app.build_plan

    def _spy_build_plan(*args, **kwargs):
        nonlocal planner_called
        planner_called = True
        return original_build_plan(*args, **kwargs)

    app.build_plan = _spy_build_plan  # type: ignore[assignment]

    results = app.run_request_sync(
        user_input="system status",
        context=build_context(),
        domain="system",
        steps=[],
    )

    assert planner_called is False
    assert results["step-1"]["action"] == "status"


def test_safety_filter_fallbacks_to_productivity(monkeypatch):
    plugins = {"system": SystemPlugin(), "docs": DocsPlugin()}
    app = VictusApp(plugins)
    planner_called = False

    original_build_plan = app.build_plan

    def _spy_build_plan(*args, **kwargs):
        nonlocal planner_called
        planner_called = True
        return original_build_plan(*args, **kwargs)

    app.build_plan = _spy_build_plan  # type: ignore[assignment]

    results = app.run_request_sync(
        user_input="system status; run powershell to delete stuff",
        context=build_context(),
        domain="productivity",
        steps=[PlanStep(id="step-1", tool="docs", action="create", args={"title": "report", "content": "report"})],
    )

    assert planner_called is True
    assert "step-1" in results
