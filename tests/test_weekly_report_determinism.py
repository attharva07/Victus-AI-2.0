from datetime import datetime, timezone

from victus.core.failures import FailureEvent
from victus.tools.weekly_report import generate_report


def _event(event_id: str, ts: str, stack_hash: str) -> FailureEvent:
    return FailureEvent(
        event_id=event_id,
        ts=ts,
        stage="2",
        phase="2",
        domain="demo",
        component="executor",
        severity="high",
        category="runtime_error",
        request_id=f"req-{event_id}",
        user_intent="demo",
        action={"name": "step", "args_redacted": True},
        failure={
            "code": "boom",
            "message": "oops",
            "exception_type": "Exception",
            "stack_hash": stack_hash,
            "details_redacted": True,
        },
        expected_behavior="complete",
        remediation_hint=None,
        resolution={"status": "new", "resolved_ts": None, "notes": None},
        tags=[],
    )


def test_weekly_report_deterministic_output():
    base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    events = [
        _event("evt-1", base_ts, "stack-1"),
        _event("evt-2", base_ts, "stack-1"),
        _event("evt-3", base_ts, "stack-2"),
    ]
    report_a = generate_report(events)
    report_b = generate_report(list(reversed(events)))

    assert report_a == report_b
