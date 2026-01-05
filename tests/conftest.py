from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_psutil_stub():
    import types

    psutil_stub = types.ModuleType("psutil")

    class AccessDenied(Exception):
        def __init__(self, pid=None, name=None):
            super().__init__("Access denied")
            self.pid = pid
            self.name = name

    class NoSuchProcess(Exception):
        pass

    class ZombieProcess(Exception):
        pass

    class Process:
        def __init__(self, pid=None):
            self.pid = pid

        def name(self):  # pragma: no cover - only used when stub active
            raise AccessDenied(pid=self.pid)

    def net_connections(kind=None):  # pragma: no cover - stub placeholder
        return []

    def disk_partitions(all=True):  # pragma: no cover - stub placeholder
        return []

    def win_service_get(name):  # pragma: no cover - stub placeholder
        raise AccessDenied()

    psutil_stub.AccessDenied = AccessDenied
    psutil_stub.NoSuchProcess = NoSuchProcess
    psutil_stub.ZombieProcess = ZombieProcess
    psutil_stub.Process = Process
    psutil_stub.net_connections = net_connections
    psutil_stub.disk_partitions = disk_partitions
    psutil_stub.win_service_get = win_service_get

    sys.modules["psutil"] = psutil_stub


def _ensure_psutil():
    try:
        import psutil  # noqa: F401
    except ImportError:  # pragma: no cover - fallback when dependency missing locally
        _install_psutil_stub()


_ensure_psutil()
