from __future__ import annotations

from typing import Any, Mapping


def _format_bytes(num: float | int | None) -> str:
    if num is None:
        return "unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} B"


def _format_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.1f}%"
    return "unknown"


def _render_cpu(data: Mapping[str, Any]) -> list[str]:
    cpu_percent = data.get("cpu_percent")
    if cpu_percent is None:
        return []
    return [f"CPU Usage: {_format_percent(cpu_percent)}"]


def _render_memory(data: Mapping[str, Any]) -> list[str]:
    used = data.get("memory_used_bytes")
    total = data.get("memory_total_bytes")
    percent = data.get("memory_percent")
    available = data.get("memory_available_bytes")
    if used is None and total is None and percent is None:
        return []

    line = "Memory Usage: "
    parts = []
    if used is not None and total is not None:
        parts.append(f"{_format_bytes(used)} / {_format_bytes(total)}")
    if percent is not None:
        parts.append(_format_percent(percent))
    line += " (".join(parts)
    line += ")" if len(parts) > 1 else ""

    details = [line]
    if available is not None:
        details.append(f"Available: {_format_bytes(available)}")
    return details


def _render_disk(data: Mapping[str, Any]) -> list[str]:
    used = data.get("disk_used_bytes")
    total = data.get("disk_total_bytes")
    free = data.get("disk_free_bytes")
    percent = data.get("disk_percent")
    path = data.get("disk_path", "/")
    if used is None and total is None and percent is None:
        return []

    line = f"Disk Space ({path}): "
    parts = []
    if used is not None and total is not None:
        parts.append(f"{_format_bytes(used)} / {_format_bytes(total)}")
    if percent is not None:
        parts.append(_format_percent(percent))
    line += " (".join(parts)
    line += ")" if len(parts) > 1 else ""

    details = [line]
    if free is not None:
        details.append(f"Free: {_format_bytes(free)}")
    return details


def render_system_result(result: Mapping[str, Any]) -> str | None:
    if not isinstance(result, Mapping) or result.get("action") != "status":
        return None

    data = result.get("data", {})
    if not isinstance(data, Mapping):
        return None

    focus = result.get("focus")
    lines: list[str] = []

    if focus in (None, "cpu"):
        lines.extend(_render_cpu(data))
    if focus in (None, "memory"):
        lines.extend(_render_memory(data))
    if focus in (None, "disk"):
        lines.extend(_render_disk(data))

    if not lines:
        return "No system metrics available"
    return "\n".join(lines)

