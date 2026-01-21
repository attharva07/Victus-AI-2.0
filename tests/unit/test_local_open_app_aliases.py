import json

from victus_local import app_aliases, task_runner


def _configure_alias_store(tmp_path, monkeypatch, aliases=None):
    seed_path = tmp_path / "app_aliases.seed.json"
    alias_path = tmp_path / "app_aliases.json"
    payload = {
        "aliases": aliases
        or {
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
        },
        "updated_at": "1970-01-01T00:00:00Z",
    }
    seed_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(app_aliases, "_SEED_FILE", seed_path)
    monkeypatch.setattr(app_aliases, "_ALIAS_FILE", alias_path)
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
    assert "Which app should I open?" in result["assistant_message"]
    assert "(1)" in result["assistant_message"]
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
    assert result["alias_learned"]["alias"] == "visual"
    stored = json.loads(alias_path.read_text(encoding="utf-8"))
    assert stored["aliases"]["calculator"] == "calc.exe"
    assert stored["aliases"]["visual"] == "code.exe"
