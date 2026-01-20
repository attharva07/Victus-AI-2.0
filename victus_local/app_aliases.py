from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

_ALIAS_FILE = Path(__file__).parent / "app_aliases.json"
_SEED_FILE = Path(__file__).parent / "app_aliases.seed.json"

_DEFAULT_ALIASES = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
}

_NORMALIZE_SPACE_RE = re.compile(r"\s+")
_SAFE_ALIAS_RE = re.compile(r"^[a-z0-9 _-]+$")


@dataclass(frozen=True)
class AppCandidate:
    label: str
    target: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class AppResolution:
    decision: str
    target: Optional[str] = None
    label: Optional[str] = None
    candidates: List[Dict[str, str]] | None = None
    source: Optional[str] = None


_KNOWN_APPS: List[AppCandidate] = [
    AppCandidate("Calculator", "calc.exe", ("calculator", "calc")),
    AppCandidate("Notepad", "notepad.exe", ("notepad",)),
    AppCandidate("Notepad++", "notepad++.exe", ("notepad++", "notepad plus plus")),
    AppCandidate("VS Code", "code.exe", ("vs code", "vscode", "visual studio code")),
    AppCandidate("Paint", "mspaint.exe", ("paint", "mspaint")),
    AppCandidate("Command Prompt", "cmd.exe", ("cmd", "command prompt")),
    AppCandidate("PowerShell", "powershell.exe", ("powershell", "pwsh", "windows powershell")),
]

_KNOWN_ALIAS_MAP: Dict[str, AppCandidate] = {}
for app in _KNOWN_APPS:
    for alias in app.aliases:
        _KNOWN_ALIAS_MAP[alias] = app
    _KNOWN_ALIAS_MAP[app.label.lower()] = app


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def normalize_app_name(value: str) -> str:
    stripped = value.strip()
    stripped = stripped.strip("\"'")
    collapsed = _NORMALIZE_SPACE_RE.sub(" ", stripped)
    return collapsed.lower()


def _load_seed_data() -> Dict[str, object]:
    if _SEED_FILE.exists():
        try:
            return json.loads(_SEED_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"aliases": dict(_DEFAULT_ALIASES), "updated_at": _now_iso()}


def _write_alias_file(payload: Dict[str, object]) -> None:
    _ALIAS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ALIAS_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_alias_store() -> Dict[str, object]:
    if not _ALIAS_FILE.exists():
        seed = _load_seed_data()
        seed["updated_at"] = _now_iso()
        _write_alias_file(seed)
        return seed

    try:
        data = json.loads(_ALIAS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = _load_seed_data()
        data["updated_at"] = _now_iso()
        _write_alias_file(data)
        return data

    aliases = data.get("aliases")
    if not isinstance(aliases, dict):
        data = _load_seed_data()
        data["updated_at"] = _now_iso()
        _write_alias_file(data)
        return data

    normalized_aliases: Dict[str, str] = {}
    for raw_key, raw_value in aliases.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            continue
        key = normalize_app_name(raw_key)
        if not key:
            continue
        normalized_aliases[key] = raw_value
    data["aliases"] = normalized_aliases
    return data


def save_alias_store(aliases: Dict[str, str]) -> None:
    payload = {"aliases": aliases, "updated_at": _now_iso()}
    _write_alias_file(payload)


def is_safe_alias(value: str) -> bool:
    normalized = normalize_app_name(value)
    if not normalized:
        return False
    if len(normalized) > 32:
        return False
    if not _SAFE_ALIAS_RE.match(normalized):
        return False
    if len(normalized.split()) > 2:
        return False
    return True


def resolve_app_target(requested: str, aliases: Dict[str, str]) -> AppResolution:
    normalized = normalize_app_name(requested)
    if not normalized:
        return AppResolution(decision="not_found")

    if normalized in aliases:
        target = aliases[normalized]
        label = _label_for_target(target) or normalized.title()
        return AppResolution(decision="open", target=target, label=label, source="alias")

    path = Path(requested).expanduser()
    if path.exists():
        return AppResolution(decision="open", target=str(path), label=path.name, source="path")

    exact = _KNOWN_ALIAS_MAP.get(normalized)
    if exact:
        return AppResolution(decision="open", target=exact.target, label=exact.label, source="known")

    for app in _KNOWN_APPS:
        if normalized == app.target.lower():
            return AppResolution(decision="open", target=app.target, label=app.label, source="known")

    partial_matches = _partial_candidates(normalized)
    if len(partial_matches) == 1:
        candidate = partial_matches[0]
        return AppResolution(decision="open", target=candidate["target"], label=candidate["label"], source="known")
    if partial_matches:
        return AppResolution(decision="clarify", candidates=partial_matches, source="known")

    return AppResolution(decision="not_found")


def build_clarify_message(candidates: Iterable[Dict[str, str]]) -> str:
    entries = list(candidates)
    if not entries:
        return "Which app should I open?"
    choices = " ".join(
        f"({index}) {candidate['label']}" for index, candidate in enumerate(entries, start=1)
    )
    return f"Which app should I open? {choices}"


def resolve_candidate_choice(
    response: str,
    candidates: Iterable[Dict[str, str]],
    aliases: Dict[str, str],
) -> Optional[Dict[str, str]]:
    entries = list(candidates)
    normalized = normalize_app_name(response)
    if not normalized:
        return None
    if normalized.isdigit():
        index = int(normalized) - 1
        if 0 <= index < len(entries):
            return entries[index]

    for candidate in entries:
        if normalize_app_name(candidate["label"]) == normalized:
            return candidate

    alias_target = aliases.get(normalized)
    if alias_target:
        for candidate in entries:
            if candidate["target"].lower() == alias_target.lower():
                return candidate
    return None


def _partial_candidates(normalized: str) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    seen_targets: set[str] = set()
    for app in _KNOWN_APPS:
        alias_hits = [alias for alias in app.aliases if normalized in alias]
        label_hit = normalized in app.label.lower()
        if alias_hits or label_hit:
            if app.target in seen_targets:
                continue
            seen_targets.add(app.target)
            matches.append({"label": app.label, "target": app.target})
    return matches


def _label_for_target(target: str) -> Optional[str]:
    for app in _KNOWN_APPS:
        if app.target.lower() == target.lower():
            return app.label
    return None
