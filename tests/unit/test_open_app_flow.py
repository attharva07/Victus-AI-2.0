import asyncio
import json

from victus.core.schemas import TurnEvent
from victus_local import app_dictionary
from victus_local.app_aliases import normalize_app_name
from victus_local.app_resolver import ResolvedCandidate
from victus_local.dialogue_state import PendingAction
from victus_local.turn_handler import SessionState, TurnHandler


class DummyApp:
    pass


def _configure_app_dictionary(tmp_path, monkeypatch, entries):
    alias_path = tmp_path / "app_dict.json"
    payload = {
        "canonical": {},
        "aliases": {},
        "candidates": {},
        "updated_at": "1970-01-01T00:00:00Z",
    }
    for entry in entries:
        payload["canonical"][entry["target"]] = {
            "label": entry["label"],
            "usage": 0,
            "last_seen": None,
        }
        for alias in entry.get("aliases", []):
            payload["aliases"][normalize_app_name(alias)] = {
                "canonical": entry["target"],
                "usage": 0,
                "last_seen": None,
            }
    alias_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(app_dictionary, "DEFAULT_PATH", alias_path)
    return alias_path


async def _collect_events(iterator):
    return [event async for event in iterator]


def test_normalize_input():
    assert normalize_app_name("  Paint!! ") == "paint"
    assert normalize_app_name("VS   Code") == "vs code"
    assert normalize_app_name("note.pad") == "note pad"


def test_resolve_single_candidate_executes(monkeypatch, tmp_path):
    _configure_app_dictionary(
        tmp_path,
        monkeypatch,
        entries=[{"label": "Paint", "target": "mspaint.exe", "aliases": ["paint"]}],
    )
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    calls = []

    async def fake_run_open_app(_message, requested_alias, target, label):
        calls.append((requested_alias, target, label))
        yield TurnEvent(event="token", token="Opening Paint.")

    handler._run_open_app = fake_run_open_app  # type: ignore[assignment]

    events = asyncio.run(_collect_events(handler._handle_open_app("open paint", session)))

    assert session.dialogue.pending is None
    assert calls == [("paint", "mspaint.exe", "Paint")]
    assert any(event.event == "token" for event in events)


def test_resolve_multiple_sets_pending_action(monkeypatch, tmp_path):
    _configure_app_dictionary(
        tmp_path,
        monkeypatch,
        entries=[
            {"label": "Notepad", "target": "notepad.exe", "aliases": ["notepad"]},
            {"label": "Notepad++", "target": "notepad++.exe", "aliases": ["notepad++"]},
        ],
    )
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    calls = []

    async def fake_run_open_app(*_args, **_kwargs):
        calls.append("called")
        yield TurnEvent(event="token", token="Opening.")

    handler._run_open_app = fake_run_open_app  # type: ignore[assignment]

    events = asyncio.run(_collect_events(handler._handle_open_app("open note", session)))

    assert calls == []
    assert session.dialogue.pending is not None
    assert session.dialogue.pending.attempts == 0
    clarify = next(event for event in events if event.event == "clarify")
    assert "(1)" not in (clarify.message or "")


def test_pending_action_consumed_executes_and_clears():
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    session.dialogue.pending = PendingAction(
        kind="open_app",
        original_text="open note",
        candidates=[
            ResolvedCandidate(name="Notepad", target="notepad.exe", score=0.9),
            ResolvedCandidate(name="Notepad++", target="notepad++.exe", score=0.8),
        ],
        created_at=0.0,
        attempts=0,
    )
    calls = []

    async def fake_run_open_app(_message, requested_alias, target, label):
        calls.append((requested_alias, target, label))
        yield TurnEvent(event="token", token="Opening Notepad.")

    handler._run_open_app = fake_run_open_app  # type: ignore[assignment]

    events = asyncio.run(_collect_events(handler._resolve_pending_action("notepad", session)))

    assert session.dialogue.pending is None
    assert calls == [("open note", "notepad.exe", "Notepad")]
    assert any(event.event == "token" for event in events)


def test_pending_action_invalid_then_abort_and_clear():
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    session.dialogue.pending = PendingAction(
        kind="open_app",
        original_text="open note",
        candidates=[
            ResolvedCandidate(name="Notepad", target="notepad.exe", score=0.9),
            ResolvedCandidate(name="Notepad++", target="notepad++.exe", score=0.8),
        ],
        created_at=0.0,
        attempts=0,
    )

    first = asyncio.run(_collect_events(handler._resolve_pending_action("unknown", session)))
    assert session.dialogue.pending is not None
    assert session.dialogue.pending.attempts == 1
    assert any(event.event == "clarify" for event in first)

    second = asyncio.run(_collect_events(handler._resolve_pending_action("still nope", session)))
    assert session.dialogue.pending is None
    assert any(event.event == "token" for event in second)


def test_no_reask_after_success(monkeypatch, tmp_path):
    _configure_app_dictionary(
        tmp_path,
        monkeypatch,
        entries=[{"label": "Paint", "target": "mspaint.exe", "aliases": ["paint"]}],
    )
    handler = TurnHandler(app=DummyApp())
    session = SessionState()
    session.dialogue.pending = PendingAction(
        kind="open_app",
        original_text="open paint",
        candidates=[ResolvedCandidate(name="Paint", target="mspaint.exe", score=0.9)],
        created_at=0.0,
        attempts=0,
    )
    calls = []

    async def fake_run_open_app(_message, requested_alias, target, label):
        calls.append((requested_alias, target, label))
        yield TurnEvent(event="token", token="Opening Paint.")

    handler._run_open_app = fake_run_open_app  # type: ignore[assignment]

    asyncio.run(_collect_events(handler._resolve_pending_action("paint", session)))
    assert session.dialogue.pending is None

    events = asyncio.run(_collect_events(handler._handle_open_app("open paint", session)))
    assert any(event.event == "token" for event in events)
    assert len(calls) == 2


def test_open_app_conversation_integration(monkeypatch, tmp_path):
    _configure_app_dictionary(
        tmp_path,
        monkeypatch,
        entries=[
            {"label": "Spotify", "target": "spotify.exe", "aliases": []},
            {"label": "Spotify Web", "target": "spotify-web.exe", "aliases": []},
            {"label": "Notepad", "target": "notepad.exe", "aliases": ["notepad"]},
        ],
    )
    handler = TurnHandler(app=DummyApp())
    calls = []

    async def fake_run_open_app(_message, requested_alias, target, label):
        calls.append((requested_alias, target, label))
        yield TurnEvent(event="token", token=f"Opening {label}.")

    handler._run_open_app = fake_run_open_app  # type: ignore[assignment]

    session_context = {"session_key": "integration"}

    first = asyncio.run(_collect_events(handler.run_turn("open spotify", context=session_context)))
    assert any(event.event == "clarify" for event in first)

    second = asyncio.run(_collect_events(handler.run_turn("spotify", context=session_context)))
    assert any(event.event == "token" for event in second)

    third = asyncio.run(_collect_events(handler.run_turn("open notepad", context=session_context)))
    assert any(event.event == "token" for event in third)
    assert len(calls) == 2
