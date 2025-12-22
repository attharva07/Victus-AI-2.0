from datetime import datetime

from victus.app import VictusApp
from victus.core.schemas import Context, PlanStep, PrivacySettings
from victus.domains.base import DummyPlugin


def build_context():
    return Context(
        session_id="session-1",
        timestamp=datetime.utcnow(),
        mode="dev",
        foreground_app=None,
        privacy=PrivacySettings(allow_screenshot=True, allow_send_to_openai=True),
    )


def test_app_runs_full_phase_one_flow():
    plugin = DummyPlugin({"open_app"})
    app = VictusApp({"system": plugin})
    step = PlanStep(id="step-1", tool="system", action="open_app", args={"app": "spotify"})

    results = app.run_request(
        user_input="open spotify",
        context=build_context(),
        domain="system",
        steps=[step],
    )

    assert results["step-1"]["action"] == "open_app"
    assert app.audit.records[-1].approval.approved is True
