from __future__ import annotations

import asyncio
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote_plus, urlparse


class TaskError(RuntimeError):
    pass


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _open_path_or_app(target: str) -> None:
    if sys.platform.startswith("win"):
        subprocess.Popen(["cmd", "/c", "start", "", target], shell=True)
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
    target = args.get("name") or args.get("path") or args.get("app")
    if not isinstance(target, str) or not target.strip():
        raise TaskError("open_app requires 'name', 'path', or 'app'")
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
    try:
        _open_path_or_app(target)
    except Exception as exc:  # noqa: BLE001
        raise TaskError(f"Unable to open app '{target}': {exc}") from exc
    return {"opened": target}


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
