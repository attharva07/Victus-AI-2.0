from __future__ import annotations

from typing import Any, Dict

from ..base import BasePlugin
from ...core.schemas import Approval, ExecutionError


class SystemPlugin(BasePlugin):
    """Allowlisted system plugin supporting open_app and net_snapshot."""

    allowed_apps = {"spotify", "notes", "browser"}
    _net_details = {"summary", "interfaces"}

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "open_app": {"app": list(self.allowed_apps)},
            "net_snapshot": {"detail": list(self._net_details)},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action == "open_app":
            self._validate_open_app(args)
        elif action == "net_snapshot":
            self._validate_net_snapshot(args)
        else:
            raise ExecutionError("Unknown system action requested")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        if action == "open_app":
            return {"action": action, "opened": args.get("app")}
        if action == "net_snapshot":
            detail = args.get("detail", "summary")
            payload = {"summary": "no anomalies", "interfaces": ["lo", "eth0"]}
            return {"action": action, "detail": detail, "data": payload[detail]}
        raise ExecutionError("Unknown system action requested")

    def _validate_open_app(self, args: Dict[str, Any]) -> None:
        app = args.get("app")
        if not isinstance(app, str) or app not in self.allowed_apps:
            raise ExecutionError("open_app requires an allowlisted 'app' string")

    def _validate_net_snapshot(self, args: Dict[str, Any]) -> None:
        detail = args.get("detail", "summary")
        if detail not in self._net_details:
            raise ExecutionError("net_snapshot detail must be 'summary' or 'interfaces'")
