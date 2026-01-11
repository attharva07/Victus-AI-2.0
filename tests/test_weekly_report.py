import re
from datetime import datetime, timedelta, timezone
from victus.core.failures import FailureEvent, FailureLogger
from victus.tools import weekly_report


def _seed_failures(tmp_path):
    logger = FailureLogger(tmp_path / "victus" / "data" / "failures")
    base_ts = datetime.now(timezone.utc)
    for idx in range(3):
        logger.append(
            FailureEvent(
                ts=(base_ts - timedelta(days=idx)).isoformat(),
                stage="2",
                phase="1",
                domain="demo",
                component="executor",
                severity="high",
                category="runtime_error",
                request_id=f"req-{idx}",
                user_intent="demo",
                action={"name": "step", "args_redacted": True},
                failure={
                    "code": "boom",
                    "message": "oops",
                    "exception_type": "Exception",
                    "stack_hash": "stack-1" if idx < 2 else "stack-2",
                    "details_redacted": True,
                },
                expected_behavior="complete",
                remediation_hint=None,
                resolution={"status": "new", "resolved_ts": None, "notes": None},
                tags=[],
            )
        )


def test_weekly_report_generates_markdown_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_failures(tmp_path)

    rc = weekly_report.main(["--week", "current"])
    assert rc == 0
    report_dir = tmp_path / "victus" / "reports" / "weekly"
    files = list(report_dir.glob("*.md"))
    assert files
    content = files[0].read_text()
    assert re.match(r"^\d{4}-W\d{2}\.md$", files[0].name)
    assert "Weekly Failure Report" in content
    assert "Totals" in content


def test_weekly_report_groups_recurring_by_stack_hash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed_failures(tmp_path)

    logger = FailureLogger(tmp_path / "victus" / "data" / "failures")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    events = list(logger.iter_events(start, end))
    report = weekly_report.generate_report(events)

    assert "stack-1" in report
    assert "2x" in report
