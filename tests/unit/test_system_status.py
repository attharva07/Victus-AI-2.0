from types import SimpleNamespace

from victus.domains.system import system_plugin
from victus.domains.system.system_plugin import SystemPlugin
from victus.ui.renderers import render_system_result


class FakePsutil:
    def __init__(self) -> None:
        self.cpu_calls: list[float | None] = []

    def cpu_percent(self, interval=None):
        self.cpu_calls.append(interval)
        if interval is None:
            return 0.0
        return 12.5

    def virtual_memory(self):
        return SimpleNamespace(total=1024, available=512, used=512, percent=50.0)

    def disk_usage(self, path):
        return SimpleNamespace(total=2048, used=1024, free=1024, percent=50.0)


def test_status_snapshot_primes_cpu_percent(monkeypatch):
    fake_psutil = FakePsutil()
    monkeypatch.setattr(system_plugin, "psutil", fake_psutil)

    plugin = SystemPlugin()
    result = plugin._status_snapshot()

    assert result["data"]["cpu_percent"] == 12.5
    assert fake_psutil.cpu_calls == [None, 0.25]


def test_status_snapshot_respects_focus(monkeypatch):
    fake_psutil = FakePsutil()
    monkeypatch.setattr(system_plugin, "psutil", fake_psutil)

    plugin = SystemPlugin()
    result = plugin._status_snapshot({"focus": "memory"})

    assert result.get("focus") == "memory"
    assert set(result["data"].keys()) == {
        "memory_used_bytes",
        "memory_total_bytes",
        "memory_available_bytes",
        "memory_percent",
    }


def test_render_system_result_formats_output():
    rendered = render_system_result(
        {
            "action": "status",
            "data": {
                "cpu_percent": 25.0,
                "memory_used_bytes": 524288000,
                "memory_total_bytes": 1073741824,
                "memory_percent": 50.0,
                "disk_used_bytes": 1073741824,
                "disk_total_bytes": 2147483648,
                "disk_percent": 50.0,
            },
        }
    )

    assert rendered is not None
    assert "CPU Usage" in rendered
    assert "Memory Usage" in rendered
    assert "Disk Space" in rendered
