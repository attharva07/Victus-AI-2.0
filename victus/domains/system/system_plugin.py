from __future__ import annotations

import platform
import socket
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Set

try:
    import psutil  # type: ignore
except ImportError as exc:  # pragma: no cover - exercised in tests via stubbing
    psutil = None  # type: ignore
    _PSUTIL_IMPORT_ERROR = exc
else:
    _PSUTIL_IMPORT_ERROR = None

from ..base import BasePlugin
from ...core.schemas import Approval, ExecutionError


PROCESS_PERMISSION_NOTE = "process mapping limited by permissions"


class SystemPlugin(BasePlugin):
    """Allowlisted system plugin supporting read-only access overview actions."""

    allowed_apps = {"spotify", "notes", "browser"}
    _net_details = {"summary", "interfaces"}

    def capabilities(self) -> Dict[str, Dict[str, Any]]:
        return {
            "status": {},
            "open_app": {"app": list(self.allowed_apps)},
            "net_snapshot": {"detail": list(self._net_details)},
            "net_connections": {},
            "exposure_snapshot": {},
            "bt_status": {},
            "local_devices": {},
            "access_overview": {},
        }

    def validate_args(self, action: str, args: Dict[str, Any]) -> None:
        if action == "open_app":
            self._validate_open_app(args)
        elif action == "net_snapshot":
            self._validate_net_snapshot(args)
        elif action == "status":
            self._validate_status(args)
        elif action in {"net_connections", "exposure_snapshot", "bt_status", "local_devices", "access_overview"}:
            return
        else:
            raise ExecutionError("Unknown system action requested")

    def execute(self, action: str, args: Dict[str, Any], approval: Approval) -> Dict[str, Any]:
        if not approval.policy_signature:
            raise ExecutionError("Missing policy signature")
        if action == "status":
            return self._status_snapshot(args)
        if action == "open_app":
            return {"action": action, "opened": args.get("app")}
        if action == "net_snapshot":
            detail = args.get("detail", "summary")
            payload = {"summary": "no anomalies", "interfaces": ["lo", "eth0"]}
            return {"action": action, "detail": detail, "data": payload[detail]}
        if action == "net_connections":
            return self._net_connections()
        if action == "exposure_snapshot":
            return self._exposure_snapshot()
        if action == "bt_status":
            return self._bluetooth_status()
        if action == "local_devices":
            return self._local_devices()
        if action == "access_overview":
            return self._access_overview()
        raise ExecutionError("Unknown system action requested")

    def _validate_open_app(self, args: Dict[str, Any]) -> None:
        app = args.get("app")
        if not isinstance(app, str) or app not in self.allowed_apps:
            raise ExecutionError("open_app requires an allowlisted 'app' string")

    def _validate_net_snapshot(self, args: Dict[str, Any]) -> None:
        detail = args.get("detail", "summary")
        if detail not in self._net_details:
            raise ExecutionError("net_snapshot detail must be 'summary' or 'interfaces'")

    def _validate_status(self, args: Dict[str, Any]) -> None:
        focus = args.get("focus")
        if focus is None:
            return
        if not isinstance(focus, str) or focus not in {"cpu", "memory", "disk"}:
            raise ExecutionError("status focus must be one of: cpu, memory, disk")

    def _status_snapshot(self, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        focus = (args or {}).get("focus")
        notes: List[str] = []
        data: Dict[str, Any] = {
            "cpu_percent": None,
            "memory_used_bytes": None,
            "memory_total_bytes": None,
            "memory_available_bytes": None,
            "memory_percent": None,
            "disk_used_bytes": None,
            "disk_total_bytes": None,
            "disk_free_bytes": None,
            "disk_percent": None,
        }

        if psutil is None:
            notes.append("psutil not available; returning placeholder metrics")
        else:
            try:
                psutil.cpu_percent(interval=None)
                data["cpu_percent"] = psutil.cpu_percent(interval=0.25)

                mem = psutil.virtual_memory()
                data["memory_used_bytes"] = mem.used
                data["memory_total_bytes"] = mem.total
                data["memory_available_bytes"] = mem.available
                data["memory_percent"] = mem.percent

                disk_path = "C:\\" if platform.system().lower() == "windows" else "/"
                disk = psutil.disk_usage(disk_path)
                data["disk_used_bytes"] = disk.used
                data["disk_total_bytes"] = disk.total
                data["disk_free_bytes"] = disk.free
                data["disk_percent"] = disk.percent
                data["disk_path"] = disk_path
            except Exception as exc:  # pragma: no cover - unexpected platform errors
                notes.append(f"Failed to collect system metrics: {exc}")

        filtered_data = self._filter_metrics_by_focus(data, focus) if focus else data
        result: Dict[str, Any] = {"ok": True, "action": "status", "data": filtered_data, "notes": notes}
        if focus:
            result["focus"] = focus
        return result

    @staticmethod
    def _filter_metrics_by_focus(metrics: Dict[str, Any], focus: str) -> Dict[str, Any]:
        focus_fields = {
            "cpu": ["cpu_percent"],
            "memory": [
                "memory_used_bytes",
                "memory_total_bytes",
                "memory_available_bytes",
                "memory_percent",
            ],
            "disk": ["disk_used_bytes", "disk_total_bytes", "disk_free_bytes", "disk_percent", "disk_path"],
        }
        if focus not in focus_fields:
            return metrics
        return {field: metrics.get(field) for field in focus_fields[focus] if field in metrics}

    def _net_connections(self) -> Dict[str, Any]:
        ps = self._require_psutil()
        notes: List[str] = []
        connections = []
        try:
            psutil_conns = ps.net_connections(kind="inet")
        except Exception as exc:  # pragma: no cover - unexpected platform errors
            raise ExecutionError(f"Failed to enumerate network connections: {exc}") from exc

        for conn in psutil_conns:
            proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"
            state = conn.status
            local_ip, local_port = self._addr_fields(conn.laddr)
            remote_ip, remote_port = self._addr_fields(conn.raddr)
            pid = conn.pid
            process_name = self._safe_process_name_with_module(pid, notes, ps)

            connections.append(
                {
                    "proto": proto,
                    "state": state,
                    "local_ip": local_ip,
                    "local_port": local_port,
                    "remote_ip": remote_ip,
                    "remote_port": remote_port,
                    "pid": pid,
                    "process_name": process_name,
                }
            )

        return {"ok": True, "action": "net_connections", "data": connections, "notes": notes}

    def _exposure_snapshot(self, *_args, connections_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        connections_result = connections_result or self._net_connections()
        notes = list(connections_result.get("notes", []))
        listening = [c for c in connections_result.get("data", []) if c.get("state") == "LISTEN"]

        grouped: Dict[tuple[int | None, int | None, str | None], Dict[str, Set[str] | List[int | None]]] = defaultdict(
            lambda: {"local_ips": set(), "protocols": set()}
        )
        for conn in listening:
            key = (conn.get("local_port"), conn.get("pid"), conn.get("process_name"))
            grouped[key]["local_ips"].add(conn.get("local_ip"))
            grouped[key]["protocols"].add(conn.get("proto"))

        services = []
        for (port, pid, name), details in grouped.items():
            services.append(
                {
                    "local_port": port,
                    "pid": pid,
                    "process_name": name,
                    "local_ips": sorted(filter(None, details["local_ips"])),
                    "protocols": sorted(details["protocols"]),
                }
            )

        rdp_enabled = self._detect_rdp()
        return {
            "ok": True,
            "action": "exposure_snapshot",
            "data": {"listening": services, "rdp_enabled": rdp_enabled},
            "notes": notes,
        }

    @staticmethod
    def _bluetooth_status() -> Dict[str, Any]:
        return {
            "ok": True,
            "action": "bt_status",
            "data": {"adapter_present": False, "connected_devices": []},
            "notes": ["Bluetooth inspection not available without platform APIs"],
        }

    def _local_devices(self) -> Dict[str, Any]:
        ps = self._require_psutil()
        notes: List[str] = []
        usb_devices: List[Dict[str, Any]] = []
        usb_supported = True
        usb_reason = ""

        try:
            for partition in ps.disk_partitions(all=True):
                if "removable" in partition.opts or partition.device.startswith("/dev/sd"):
                    usb_devices.append(
                        {
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                        }
                    )
        except Exception as exc:  # pragma: no cover - platform-specific
            usb_supported = False
            usb_reason = f"psutil cannot enumerate devices: {exc}"

        bluetooth_supported = False
        bluetooth_reason = "Bluetooth inspection not available without platform APIs"
        bluetooth_adapter_present = False
        bluetooth_connections: List[str] = []

        bluetooth = {
            "supported": bluetooth_supported,
            "adapter_present": bluetooth_adapter_present,
            "connected_devices": bluetooth_connections,
            "reason": bluetooth_reason,
        }

        usb = {
            "supported": usb_supported,
            "devices": usb_devices,
        }
        if not usb_supported:
            usb["reason"] = usb_reason

        return {
            "ok": True,
            "action": "local_devices",
            "data": {"usb": usb, "bluetooth": bluetooth},
            "notes": notes,
        }

    def _access_overview(self) -> Dict[str, Any]:
        connections_result = self._net_connections()
        exposure_result = self._exposure_snapshot(connections_result=connections_result)
        local_devices = self._local_devices()

        connections = connections_result.get("data", [])
        established = sum(1 for conn in connections if conn.get("state") == "ESTABLISHED")
        listening = sum(1 for conn in connections if conn.get("state") == "LISTEN")
        unique_remote_ips = len({conn.get("remote_ip") for conn in connections if conn.get("remote_ip")})

        counts = Counter((conn.get("pid"), conn.get("process_name")) for conn in connections if conn.get("pid"))
        top_processes = [
            {
                "pid": pid,
                "process_name": name,
                "connection_count": count,
            }
            for (pid, name), count in counts.most_common(5)
        ]

        notes = self._merge_notes(
            connections_result.get("notes", []), exposure_result.get("notes", []), local_devices.get("notes", [])
        )

        return {
            "ok": True,
            "action": "access_overview",
            "data": {
                "summary": {
                    "established": established,
                    "listening": listening,
                    "unique_remote_ips": unique_remote_ips,
                },
                "top_processes": top_processes,
                "net_connections": connections_result.get("data", []),
                "exposure_snapshot": exposure_result.get("data", {}),
                "local_devices": local_devices.get("data", {}),
            },
            "notes": notes,
        }

    @staticmethod
    def _addr_fields(addr: Any) -> tuple[str | None, int | None]:
        if not addr:
            return None, None
        if isinstance(addr, tuple):  # pragma: no cover - legacy psutil tuple form
            ip, port = addr
            return ip, port
        return getattr(addr, "ip", None), getattr(addr, "port", None)

    def _safe_process_name(self, pid: int | None, notes: List[str]) -> str | None:
        return self._safe_process_name_with_module(pid, notes, psutil)

    def _safe_process_name_with_module(self, pid: int | None, notes: List[str], ps) -> str | None:
        if not pid or ps is None:
            return None
        try:
            return ps.Process(pid).name()
        except ps.AccessDenied:
            self._append_note(notes, PROCESS_PERMISSION_NOTE)
            return None
        except (ps.NoSuchProcess, ps.ZombieProcess):
            return None

    @staticmethod
    def _detect_rdp() -> bool | None:
        if platform.system().lower() != "windows":
            return None
        try:
            ps = SystemPlugin._require_psutil()
            service = ps.win_service_get("TermService")
            return service.status().lower() == "running"
        except Exception:  # pragma: no cover - best-effort only
            return None

    @staticmethod
    def _require_psutil():
        if psutil is None:
            raise ExecutionError("psutil is required for this action") from _PSUTIL_IMPORT_ERROR
        return psutil

    @staticmethod
    def _append_note(notes: List[str], note: str) -> None:
        if note not in notes:
            notes.append(note)

    @staticmethod
    def _merge_notes(*note_lists: Iterable[str]) -> List[str]:
        seen: Set[str] = set()
        merged: List[str] = []
        for note_list in note_lists:
            for note in note_list:
                if note not in seen:
                    seen.add(note)
                    merged.append(note)
        return merged
