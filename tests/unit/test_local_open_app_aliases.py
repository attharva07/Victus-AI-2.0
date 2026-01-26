import json

from victus_local import app_dictionary, task_runner


def _configure_alias_store(tmp_path, monkeypatch, aliases=None):
    alias_path = tmp_path / "app_dict.json"
    payload = {
        "canonical": {
            "calc.exe": {"label": "Calculator", "usage": 0, "last_seen": None},
            "notepad.exe": {"label": "Notepad", "usage": 0, "last_seen": None},
            "code.exe": {"label": "VS Code", "usage": 0, "last_seen": None},
        },
        "aliases": aliases
        or {
            "calculator": {"canonical": "calc.exe", "usage": 0, "last_seen": None},
            "notepad": {"canonical": "notepad.exe", "usage": 0, "last_seen": None},
            "visual studio code": {"canonical": "code.exe", "usage": 0, "last_seen": None},
        },
        "candidates": {},
        "updated_at": "1970-01-01T00:00:00Z",
    }
    alias_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(app_dictionary, "DEFAULT_PATH", alias_path)
    return alias_path


def test_open_app_alias_immediate(monkeypatch, tmp_path):
    _configure_alias_store(tmp_path, monkeypatch)
    opened = {}

    def fake_open(target):
        opened["target"] = target

    monkeypatch.setattr(task_runner, "_open_path_or_app", fake_open)

    result = task_runner._open_app({"name": "calculator"})

    assert result["opened"] == "calc.exe"
    assert result["assistant_message"] == "Opened Calculator."
    assert opened["target"] == "calc.exe"


def test_open_app_clarify_on_multiple_matches(monkeypatch, tmp_path):
    _configure_alias_store(tmp_path, monkeypatch)

    result = task_runner._open_app({"name": "note"})

    assert result["decision"] == "clarify"
    assert "Which one should I open?" in result["assistant_message"]
    assert "(1)" not in result["assistant_message"]
    assert len(result["candidates"]) > 1


def test_open_app_learns_alias_after_success(monkeypatch, tmp_path):
    alias_path = _configure_alias_store(tmp_path, monkeypatch)
    opened = {}

    def fake_open(target):
        opened["target"] = target

    monkeypatch.setattr(task_runner, "_open_path_or_app", fake_open)

    result = task_runner._open_app({"name": "visual"})

    assert opened["target"] == "code.exe"
    assert result["opened"] == "code.exe"
    stored = json.loads(alias_path.read_text(encoding="utf-8"))
    assert stored["aliases"]["calculator"]["canonical"] == "calc.exe"
    assert stored["candidates"]["visual"]["canonical"] == "code.exe"
