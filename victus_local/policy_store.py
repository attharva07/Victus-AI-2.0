from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from victus.core.policy import PolicyEngine


def _flatten_allowlist(allowlist: Dict[str, Set[str]]) -> Set[str]:
    flattened: Set[str] = set()
    for tool, actions in allowlist.items():
        for action in actions:
            flattened.add(f"{tool}.{action}")
    return flattened


def _expand_allowlist(actions: Iterable[str]) -> Dict[str, Set[str]]:
    expanded: Dict[str, Set[str]] = {}
    for action in actions:
        if "." not in action:
            continue
        tool, name = action.split(".", 1)
        expanded.setdefault(tool, set()).add(name)
    return expanded


@dataclass
class PolicyState:
    enabled_actions: List[str]
    toggleable_actions: List[str]
    effective_actions: List[str]
    updated_at: str

    def as_response(self) -> Dict[str, object]:
        enabled_set = set(self.enabled_actions)
        return {
            "enabled_actions": self.enabled_actions,
            "effective_actions": self.effective_actions,
            "toggleable_actions": [
                {"action": action, "enabled": action in enabled_set} for action in self.toggleable_actions
            ],
            "updated_at": self.updated_at,
        }


class PolicyStore:
    def __init__(self, runtime_path: Path | None = None) -> None:
        self.runtime_path = runtime_path or Path(__file__).parent / "runtime_policy.json"
        self.base_allowlist = PolicyEngine().allowlist
        self.critical_denylist: Set[str] = {"raw_shell", "kernel_exec", "firewall_modify"}

    def get_toggleable_actions(self) -> List[str]:
        base_actions = _flatten_allowlist(self.base_allowlist)
        toggleable = base_actions - self.critical_denylist
        return sorted(toggleable)

    def load_runtime_policy(self) -> Dict[str, object]:
        if not self.runtime_path.exists():
            policy = self._default_runtime_policy()
            self._write_runtime_policy(policy)
            return policy
        try:
            data = json.loads(self.runtime_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            policy = self._default_runtime_policy()
            self._write_runtime_policy(policy)
            return policy
        if not isinstance(data, dict) or "enabled_actions" not in data:
            policy = self._default_runtime_policy()
            self._write_runtime_policy(policy)
            return policy
        enabled_actions = data.get("enabled_actions")
        if not isinstance(enabled_actions, list):
            enabled_actions = []
        updated_at = data.get("updated_at")
        if not isinstance(updated_at, str):
            updated_at = datetime.utcnow().isoformat() + "Z"
        return {"enabled_actions": enabled_actions, "updated_at": updated_at}

    def get_state(self) -> PolicyState:
        runtime = self.load_runtime_policy()
        enabled_actions = self._sanitize_enabled_actions(runtime.get("enabled_actions", []))
        toggleable_actions = self.get_toggleable_actions()
        effective_actions = self._compute_effective_actions(enabled_actions)
        updated_at = runtime.get("updated_at") or datetime.utcnow().isoformat() + "Z"
        return PolicyState(
            enabled_actions=enabled_actions,
            toggleable_actions=toggleable_actions,
            effective_actions=effective_actions,
            updated_at=updated_at,
        )

    def update_enabled_actions(self, actions: Iterable[str]) -> Tuple[PolicyState, List[str], List[str]]:
        sanitized = self._sanitize_enabled_actions(actions)
        previous_state = self.get_state()
        updated_at = datetime.utcnow().isoformat() + "Z"
        payload = {"enabled_actions": sanitized, "updated_at": updated_at}
        self._write_runtime_policy(payload)
        next_state = self.get_state()
        prev_enabled = set(previous_state.enabled_actions)
        next_enabled = set(next_state.enabled_actions)
        enabled = sorted(next_enabled - prev_enabled)
        disabled = sorted(prev_enabled - next_enabled)
        return next_state, enabled, disabled

    def build_effective_allowlist(self) -> Dict[str, Set[str]]:
        state = self.get_state()
        return _expand_allowlist(state.effective_actions)

    def _compute_effective_actions(self, enabled_actions: Iterable[str]) -> List[str]:
        base_actions = _flatten_allowlist(self.base_allowlist)
        enabled_set = set(enabled_actions)
        effective = base_actions & enabled_set
        effective -= self.critical_denylist
        return sorted(effective)

    def _sanitize_enabled_actions(self, actions: Iterable[str]) -> List[str]:
        toggleable = set(self.get_toggleable_actions())
        sanitized = [action for action in actions if isinstance(action, str) and action in toggleable]
        return sorted(set(sanitized))

    def _default_runtime_policy(self) -> Dict[str, object]:
        return {
            "enabled_actions": self.get_toggleable_actions(),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    def _write_runtime_policy(self, payload: Dict[str, object]) -> None:
        self.runtime_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
