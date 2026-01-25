import asyncio

from victus.core.schemas import TurnEvent
from victus_local.dialogue_state import PendingAction
from victus_local.app_resolver import ResolvedCandidate
from victus_local.turn_handler import SessionState, TurnHandler


class DummyApp:
    pass


def test_pending_resolution_flow():
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    session.dialogue.pending = PendingAction(
        kind="clarify_open_app",
        original_text="open calculator",
        candidates=[
            ResolvedCandidate(name="Calculator", target="calc.exe", score=0.9),
            ResolvedCandidate(name="Notepad", target="notepad.exe", score=0.7),
        ],
        created_at=0.0,
    )

    async def _fake_run_open_app(_message, _requested_alias, _target, _label):
        yield TurnEvent(event="token", token="Opened Calculator.")

    handler._run_open_app = _fake_run_open_app  # type: ignore[assignment]

    async def _collect():
        events = []
        async for event in handler._resolve_pending_action("calculator!!!!!", session):
            events.append(event)
        return events

    events = asyncio.run(_collect())
    assert session.dialogue.pending is None
    assert any(event.event == "token" for event in events)
