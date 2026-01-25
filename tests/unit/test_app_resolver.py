import json

from victus_local import app_dictionary
from victus_local.app_resolver import ResolvedCandidate, resolve_app_name, resolve_from_candidates


def _configure_alias_store(tmp_path, monkeypatch):
    alias_path = tmp_path / "app_dict.json"
    payload = {
        "canonical": {
            "calc.exe": {"label": "Calculator", "usage": 0, "last_seen": None},
            "notepad.exe": {"label": "Notepad", "usage": 0, "last_seen": None},
            "code.exe": {"label": "VS Code", "usage": 0, "last_seen": None},
        },
        "aliases": {
            "calculator": {"canonical": "calc.exe", "usage": 0, "last_seen": None},
            "calc": {"canonical": "calc.exe", "usage": 0, "last_seen": None},
            "notepad": {"canonical": "notepad.exe", "usage": 0, "last_seen": None},
            "visual studio code": {"canonical": "code.exe", "usage": 0, "last_seen": None},
        },
        "candidates": {},
        "updated_at": "1970-01-01T00:00:00Z",
    }
    alias_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(app_dictionary, "DEFAULT_PATH", alias_path)
    return alias_path


def test_resolve_app_name_exact_and_normalized(monkeypatch, tmp_path):
    _configure_alias_store(tmp_path, monkeypatch)

    direct = resolve_app_name("calculator")
    assert direct.match
    assert direct.match.target == "calc.exe"
    assert direct.confidence >= 0.85

    punctuated = resolve_app_name("calculator!!!!!")
    assert punctuated.match
    assert punctuated.match.target == "calc.exe"

    alias = resolve_app_name("Calc")
    assert alias.match
    assert alias.match.target == "calc.exe"

    prefixed = resolve_app_name("open calc")
    assert prefixed.match
    assert prefixed.match.target == "calc.exe"


def test_resolve_app_name_confidence_thresholds(monkeypatch, tmp_path):
    _configure_alias_store(tmp_path, monkeypatch)

    ambiguous = resolve_app_name("note")
    assert ambiguous.confidence >= 0.6
    assert ambiguous.confidence < 0.85
    assert len(ambiguous.candidates) >= 1

    unknown = resolve_app_name("totally unknown")
    assert unknown.confidence < 0.6


def test_resolve_from_candidates(monkeypatch, tmp_path):
    _configure_alias_store(tmp_path, monkeypatch)
    candidates = [
        ResolvedCandidate(name="Calculator", target="calc.exe", score=0.9),
        ResolvedCandidate(name="Notepad", target="notepad.exe", score=0.7),
    ]

    resolved = resolve_from_candidates("calculator!!!!!", candidates)
    assert resolved
    assert resolved.target == "calc.exe"

    by_index = resolve_from_candidates("2", candidates)
    assert by_index
    assert by_index.target == "notepad.exe"
