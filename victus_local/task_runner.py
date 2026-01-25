from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus, urlparse

from .app_aliases import example_candidates, normalize_app_name
from .app_dictionary import load_app_dictionary
from .app_resolver import build_candidate_prompt, build_clarify_candidates, resolve_app_name


class TaskError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _open_path_or_app(target: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(target)  # noqa: S606
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", target])
        return

    path = Path(target)
    if path.exists():
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])
        else:
            subprocess.Popen([str(path)])
        return

    subprocess.Popen(["xdg-open", target])


def _focus_windows_app(target: str) -> bool:
    time.sleep(0.5)
    try:
        import win32gui  # type: ignore[import-untyped]

        target_lower = target.lower()
        matches = []

        def _enum_handler(hwnd: int, _ctx: Any) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if title and target_lower in title.lower():
                matches.append(hwnd)

        win32gui.EnumWindows(_enum_handler, None)
        if matches:
            win32gui.SetForegroundWindow(matches[0])
            return True
    except Exception:
        pass

    try:
        import ctypes

        user32 = ctypes.windll.user32
        target_lower = target.lower()
        handles = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def _enum_windows(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value
            if title and target_lower in title.lower():
                handles.append(hwnd)
            return True

        user32.EnumWindows(_enum_windows, 0)
        if handles:
            user32.SetForegroundWindow(handles[0])
            return True
    except Exception:
        return False

    return False


def _open_youtube(query_or_url: str) -> str:
    if _is_url(query_or_url):
        webbrowser.open(query_or_url)
        return query_or_url
    url = f"https://www.youtube.com/results?search_query={quote_plus(query_or_url)}"
    webbrowser.open(url)
    return url


def _validate_action(action: str) -> None:
    if action not in {"open_app", "open_youtube"}:
        raise TaskError(f"Action '{action}' is not allowlisted")


def _validate_open_app_args(args: Dict[str, Any]) -> str:
    target = args.get("name") or args.get("app_name") or args.get("app") or args.get("path")
    if not isinstance(target, str) or not target.strip():
        raise TaskError("open_app requires 'name' or 'app_name'")
    return target


def _validate_open_youtube_args(args: Dict[str, Any]) -> str:
    query = args.get("query") or args.get("url")
    if not isinstance(query, str) or not query.strip():
        raise TaskError("open_youtube requires 'query' or 'url'")
    return query


def validate_task_args(action: str, args: Dict[str, Any]) -> None:
    _validate_action(action)
    if action == "open_app":
        _validate_open_app_args(args)
    elif action == "open_youtube":
        _validate_open_youtube_args(args)


def _open_app(args: Dict[str, Any]) -> Dict[str, Any]:
    target = _validate_open_app_args(args)
    requested_alias = str(args.get("requested_alias") or target)
    label_hint = args.get("label")
    dictionary = load_app_dictionary()
    resolution = resolve_app_name(target, dictionary)
    candidates = build_clarify_candidates(resolution.candidates)
    if resolution.confidence >= 0.6 and resolution.confidence < 0.85:
        return {
            "decision": "clarify",
            "assistant_message": build_candidate_prompt(resolution.candidates),
            "candidates": candidates,
            "original": requested_alias,
            "resolution": {"source": "fuzzy"},
        }
    if resolution.confidence < 0.6 or not resolution.match:
        examples = example_candidates()
        message = (
            f"I couldn't find an app named '{requested_alias}'. "
            "Which app should I open? Examples: Calculator, Notepad, VS Code."
        )
        return {
            "decision": "clarify",
            "assistant_message": message,
            "candidates": candidates or examples,
            "original": requested_alias,
            "resolution": {"source": "none"},
        }

    target = resolution.match.target
    label = resolution.match.name or label_hint or requested_alias
    try:
        _open_path_or_app(target)
    except Exception as exc:  # noqa: BLE001
        raise TaskError(f"Unable to open app '{target}': {exc}") from exc

    alias_learned = dictionary.record_success(requested_alias, target, label)
    normalized_alias = normalize_app_name(requested_alias)

    assistant_message = f"Opened {label}."
    response = {
        "opened": target,
        "assistant_message": assistant_message,
        "resolution": {"source": "fuzzy", "alias": normalized_alias},
    }
    if alias_learned:
        response["alias_learned"] = alias_learned
    return response


def _open_youtube_task(args: Dict[str, Any]) -> Dict[str, Any]:
    query = _validate_open_youtube_args(args)
    try:
        opened = _open_youtube(query)
    except Exception as exc:  # noqa: BLE001
        raise TaskError(f"Unable to open YouTube for '{query}': {exc}") from exc
    return {"opened": opened}


async def run_task(action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    validate_task_args(action, args)

    if action == "open_app":
        return await asyncio.to_thread(_open_app, args)
    if action == "open_youtube":
        return await asyncio.to_thread(_open_youtube_task, args)

    raise TaskError(f"Unhandled action: {action}")
