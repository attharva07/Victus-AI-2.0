from datetime import datetime, timezone

from victus.core.failures import FailureEvent
from victus.tools.weekly_report import generate_report


def test_weekly_report_includes_regression_suggestions():
    base_ts = datetime.now(timezone.utc).isoformat()
    long_message = "oops " * 40

    events = []
    for idx in range(3):
        events.append(
            FailureEvent(
                event_id=f"evt-{idx}",
                ts=base_ts,
                stage="2",
                phase="2",
                domain="demo",
                component="executor",
                severity="high",
                category="runtime_error",
                request_id=f"req-{idx}",
                user_intent="demo",
                action={"name": "step", "args_redacted": True},
                failure={
                    "code": "boom",
                    "message": long_message,
                    "note": "oops",
                    "exception_type": "Exception",
                    "stack_hash": "stack-1",
                    "details_redacted": True,
                },
                expected_behavior="complete",
                remediation_hint=None,
                resolution={"status": "new", "resolved_ts": None, "notes": None},
                tags=[],
            )
        )

    report = generate_report(events)
    assert "Suggested Regression Tests" in report
    assert "stack-1" in report
    assert "evt-0" in report
    assert "recommended_target: victus/core/executor.py" in report
    assert "example_details:" in report
