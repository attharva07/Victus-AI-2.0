"""Generate weekly failure summaries."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from victus.core.failures import FailureEvent, FailureLogger


def _parse_week(value: str) -> Tuple[datetime, datetime]:
    if value == "current":
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        return start, end

    try:
        year_str, week_str = value.split("-W")
        year = int(year_str)
        week = int(week_str)
        start = datetime.fromisocalendar(year, week, 1).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=7)
        return start, end
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"Invalid week format: {value}") from exc


def _group_recurring(events: Iterable[FailureEvent]):
    groups: Dict[str, Dict[str, object]] = {}
    for event in events:
        stack_hash = event.failure.get("stack_hash")
        key = stack_hash or f"{event.failure.get('code')}:{event.component}"
        groups.setdefault(key, {"count": 0, "example": event, "events": []})
        groups[key]["count"] += 1
        groups[key]["events"].append(event)
    for data in groups.values():
        data["events"].sort(key=lambda e: (e.ts or "", e.event_id or ""))

        data["events"].sort(key=lambda e: (e.ts, e.event_id))
    return groups


def _format_totals(events: Iterable[FailureEvent]) -> str:
    events = list(events)
    totals = Counter()
    by_domain = Counter()
    by_severity = Counter()
    by_category = Counter()
    for event in events:
        totals["total"] += 1
        by_domain[event.domain] += 1
        by_severity[event.severity] += 1
        by_category[event.category] += 1

    lines = ["## Totals", f"- Total: {totals['total']}"]
    lines.append("- By domain:")
    for domain, count in sorted(by_domain.items()):
        lines.append(f"  - {domain}: {count}")
    lines.append("- By severity:")
    for severity, count in sorted(by_severity.items()):
        lines.append(f"  - {severity}: {count}")
    lines.append("- By category:")
    for category, count in sorted(by_category.items()):
        lines.append(f"  - {category}: {count}")
    return "\n".join(lines)


def _format_recurring(groups: Dict[str, Dict[str, object]]) -> str:
    lines = ["## Top recurring issues"]
    if not groups:
        lines.append("- None recorded")
        return "\n".join(lines)

    sorted_groups = sorted(groups.items(), key=lambda item: (-item[1]["count"], item[0]))
    for key, data in sorted_groups:
        example: FailureEvent = data["example"]
        lines.append(
            f"- {data['count']}x — component={example.component}, code={example.failure.get('code')}, key={key}"
        )
    return "\n".join(lines)


def _format_policy(events: Iterable[FailureEvent]) -> str:
    lines = ["## Policy-related failures"]
    filtered = [e for e in events if e.category == "policy_violation"]
    if not filtered:
        lines.append("- None")
        return "\n".join(lines)
    for event in filtered:
        lines.append(
            f"- [{event.component}] {event.failure.get('code')}: {event.failure.get('message')} (request={event.request_id})"
        )
    return "\n".join(lines)


def _format_backlog(groups: Dict[str, Dict[str, object]]) -> str:
    lines = ["## Suggested backlog items"]
    any_items = False
    for key, data in sorted(groups.items(), key=lambda item: (-item[1]["count"], item[0])):
        if data["count"] >= 3:
            any_items = True
            example: FailureEvent = data["example"]
            lines.append(f"- Investigate {key} affecting {example.component} ({data['count']} occurrences)")
    if not any_items:
        lines.append("- None above threshold")
    return "\n".join(lines)


def _infer_test_target(event: FailureEvent) -> str:
    component = event.component
    if component == "executor":
        return "victus/core/executor.py"
    if component in {"router", "policy"}:
        return "victus/app.py"
    if component == "memory":
        return "victus/core/memory/"
    if component in {"tool", "parser"}:
        return "victus/core/"
    return f"victus/domains/{event.domain}/"


def _short_message(message: str | None, limit: int = 120) -> str:
    if not message:
        return ""
    compact = " ".join(message.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}…"

    if component:
        return f"victus.core.{component}"
    return f"victus.domains.{event.domain}"


def _format_regression_suggestions(groups: Dict[str, Dict[str, object]]) -> str:
    lines = ["## Suggested Regression Tests"]
    suggestions: List[Tuple[str, Dict[str, object]]] = [
        item for item in groups.items() if item[1]["count"] >= 3
    ]
    if not suggestions:
        lines.append("- None above threshold")
        return "\n".join(lines)
    for key, data in sorted(suggestions, key=lambda item: (-item[1]["count"], item[0])):
        events: List[FailureEvent] = data["events"]
        example: FailureEvent = data["example"]
        event_ids = [event.event_id for event in events[:3]]
        target = _infer_test_target(example)
        message = _short_message(example.failure.get("message"))
        lines.append(f"- signature: {key}")
        lines.append(f"  - count: {data['count']}")
        lines.append(f"  - example_event_ids: {', '.join(event_ids)}")
        lines.append(
            f"  - example_details: component={example.component}, code={example.failure.get('code')}, message={message}"
        )
        lines.append(f"- signature: {key}")
        lines.append(f"  - count: {data['count']}")
        lines.append(f"  - example_event_ids: {', '.join(event_ids)}")
        lines.append(f"  - recommended_target: {target}")
    return "\n".join(lines)


def generate_report(events: Iterable[FailureEvent]) -> str:
    events_list = list(events)
    recurring = _group_recurring(events_list)
    parts = [
        "# Weekly Failure Report",
        _format_totals(events_list),
        _format_recurring(recurring),
        _format_policy(events_list),
        _format_backlog(recurring),
        _format_regression_suggestions(recurring),
    ]
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate weekly failure report")
    parser.add_argument("--week", default="current", help='"current" or ISO week like 2026-W02')
    args = parser.parse_args(argv)

    start, end = _parse_week(args.week)
    logger = FailureLogger(Path("victus/data/failures"))
    events = list(logger.iter_events(start, end))

    report_body = generate_report(events)

    iso = start.isocalendar()
    report_path = Path("victus/reports/weekly") / f"{iso.year:04d}-W{iso.week:02d}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_body, encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
