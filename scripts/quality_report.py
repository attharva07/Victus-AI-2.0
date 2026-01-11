from __future__ import annotations

import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

from victus.core.failures import FailureLogger
from victus.core.memory import proposals

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from victus.core.failures import FailureLogger
from victus.core.memory import proposals

DOCS_PATH = ROOT / "docs" / "QUALITY_REPORT.md"
FAILURES_DIR = ROOT / "victus" / "data" / "failures"
PROPOSALS_DIR = ROOT / "victus" / "data" / "memory" / "proposals"
WEEKLY_REPORT_DIR = ROOT / "victus" / "reports" / "weekly"


@dataclass
class CheckResult:
    name: str
    command: List[str]
    passed: bool
    output: str
    note: str = ""


def _run_command(command: List[str]) -> Tuple[bool, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    output = f"{result.stdout}{result.stderr}".strip()
    return result.returncode == 0, output


def _parse_coverage(output: str) -> Tuple[str, List[str]]:
    percent = ""
    uncovered: List[str] = []
    lines = [line for line in output.splitlines() if line.strip()]
    for line in lines:
        stripped = line.strip()
        if "TOTAL" in stripped.split():
            parts = stripped.split()
            for part in reversed(parts):
                if part.endswith("%"):
                    percent = part
                    break
            break
    started = False
    for line in lines:
        stripped = line.strip()
        if not started and "Name" in stripped and "Stmts" in stripped:
            started = True
            continue
        if not started or stripped.startswith("Total"):
            continue
        if stripped.startswith("-" * 2):
            continue
        if stripped.startswith("TOTAL"):
            break
        if "%" in stripped:
            uncovered.append(stripped)
    return percent, uncovered[:20]


def _collect_failed_tests(output: str) -> List[str]:
    failures: List[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED") or line.startswith("ERROR"):
            failures.append(line)
    return failures[:10]


def _git_commit() -> str:
    ok, output = _run_command(["git", "rev-parse", "--short", "HEAD"])
    if ok and output:
        commit = output.splitlines()[0]
        dirty_ok, status = _run_command(["git", "status", "--porcelain"])
        if dirty_ok and status:
            commit = f"{commit} (dirty)"
        return commit
    return "(unknown)"


def _write_report(checks: List[CheckResult], coverage: str, uncovered: List[str], failures: List[str]) -> None:
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    commit_hash = _git_commit()
    python_version = platform.python_version()
    failures_last_week = _count_failures_last_week()
    new_proposals = _count_new_proposals()
    latest_report = _latest_weekly_report()
    recurring_signatures = _count_recurring_signatures_last_week()


    lines = [
        "# Victus Quality Report",
        "",
        f"Generated: {timestamp}",
        f"Commit: {commit_hash}",
        f"Python: {python_version}",
        "",
        "## Summary",
        "| Check | Status | Notes |",
        "| --- | --- | --- |",
    ]

    for check in checks:
        status = "✅ Pass" if check.passed else "❌ Fail"
        note = check.note or (check.output.splitlines()[0] if check.output else "")
        lines.append(f"| {check.name} | {status} | {note} |")

    lines.extend(
        [
            "",
            "## Operational Metrics",
            f"- Failures in last 7 days: {failures_last_week}",
            f"- New memory proposals: {new_proposals}",
            f"- Latest weekly report: {latest_report}",
            f"- Recurring signatures >=3 in last 7 days: {recurring_signatures}",

        ]
    )

    lines.extend(["", "## Coverage", f"Reported coverage: {coverage or 'unknown'}"])
    if uncovered:
        lines.append("Top uncovered lines:")
        for miss in uncovered:
            lines.append(f"- {miss}")
    else:
        lines.append("Top uncovered lines: none (full coverage reported)")

    if failures:
        lines.extend(["", "## Failing Tests", *[f"- {line}" for line in failures]])

    DOCS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _count_failures_last_week() -> int:
    if not FAILURES_DIR.exists():
        return 0
    logger = FailureLogger(FAILURES_DIR)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    return sum(1 for _ in logger.iter_events(start, end))


def _count_new_proposals() -> int:
    if not PROPOSALS_DIR.exists():
        return 0
    try:
        return len(proposals.list_proposals(PROPOSALS_DIR, status="new"))
    except Exception:
        return 0

    return len(proposals.list_proposals(PROPOSALS_DIR, status="new"))


def _latest_weekly_report() -> str:
    if not WEEKLY_REPORT_DIR.exists():
        return "none"
    pattern = re.compile(r"^\\d{4}-W\\d{2}\\.md$|^\\d{4}-\\d{2}\\.md$")
    reports = [path for path in WEEKLY_REPORT_DIR.glob("*.md") if pattern.match(path.name)]
    if not reports:
        return "none"
    latest = max(reports, key=lambda path: path.stat().st_mtime)
    return latest.name


def _count_recurring_signatures_last_week() -> int:
    if not FAILURES_DIR.exists():
        return 0
    logger = FailureLogger(FAILURES_DIR)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    counts: dict[str, int] = {}
    for event in logger.iter_events(start, end):
        stack_hash = event.failure.get("stack_hash")
        key = stack_hash or f"{event.failure.get('code')}:{event.component}"
        counts[key] = counts.get(key, 0) + 1
    return sum(1 for count in counts.values() if count >= 3)

    reports = sorted(WEEKLY_REPORT_DIR.glob("*.md"))
    if not reports:
        return "none"
    return reports[-1].name


def main() -> int:
    checks: List[CheckResult] = []

    tests_passed, tests_output = _run_command(["pytest", "-q", "--disable-warnings"])
    test_failures = _collect_failed_tests(tests_output)
    checks.append(
        CheckResult(
            name="Tests (quiet)",
            command=["pytest", "-q", "--disable-warnings"],
            passed=tests_passed,
            output=tests_output,
        )
    )

    cov_passed, cov_output = _run_command(
        ["pytest", "--cov=victus", "--cov-report=term-missing", "--cov-report=xml"]
    )
    coverage_percent, uncovered = _parse_coverage(cov_output)
    checks.append(
        CheckResult(
            name="Coverage", command=["pytest", "--cov=victus", "--cov-report=term-missing", "--cov-report=xml"], passed=cov_passed, output=cov_output, note=coverage_percent
        )
    )

    lint_passed, lint_output = _run_command(["ruff", "check", "."])
    checks.append(
        CheckResult(
            name="Ruff lint", command=["ruff", "check", "."], passed=lint_passed, output=lint_output
        )
    )

    _write_report(checks, coverage_percent, uncovered, test_failures)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
