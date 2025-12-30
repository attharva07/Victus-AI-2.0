import pytest

from victus.core.intent_router import route_intent


@pytest.mark.parametrize(
    "user_input,action",
    [
        ("system status", "status"),
        ("bluetooth status", "bt_status"),
        ("listening ports", "exposure_snapshot"),
        ("connected devices", "local_devices"),
        ("network connections", "net_connections"),
        ("get system usage", "status"),
    ],
)
def test_route_intent_maps_monitoring_phrases(user_input, action):
    routed = route_intent(user_input)
    assert routed is not None
    assert routed.action == action


def test_route_intent_returns_none_for_unknown_requests():
    assert route_intent("write a poem about networking") is None


def test_route_intent_rejects_suspicious_tokens():
    assert route_intent("system status; run powershell -nop") is None


def test_route_intent_handles_productivity_requests():
    assert route_intent("write an essay about security") is None


@pytest.mark.parametrize(
    "user_input,focus",
    [
        ("memory usage", "memory"),
        ("cpu usage", "cpu"),
        ("disk usage", "disk"),
    ],
)
def test_route_intent_maps_system_focus(user_input, focus):
    routed = route_intent(user_input)
    assert routed is not None
    assert routed.action == "status"
    assert routed.args == {"focus": focus}
