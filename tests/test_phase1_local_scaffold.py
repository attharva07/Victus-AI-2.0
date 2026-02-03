from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import ensure_directories
from core.vault.sandbox import VaultPathError, safe_join


def test_data_dir_creation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    paths = ensure_directories()
    assert paths.base_dir.exists()
    assert paths.data_dir.exists()
    assert paths.logs_dir.exists()
    assert paths.vault_dir.exists()


def test_vault_path_safety(tmp_path: Path) -> None:
    base = tmp_path / "vault"
    base.mkdir()
    safe = safe_join(base, "allowed", "file.txt", allowlist=["allowed"])
    assert safe.parent == (base / "allowed").resolve()

    with pytest.raises(VaultPathError):
        safe_join(base, "..", "escape.txt")

    external = tmp_path / "outside"
    external.mkdir()
    link = base / "link"
    try:
        os.symlink(external, link)
    except (OSError, NotImplementedError):
        return

    with pytest.raises(VaultPathError):
        safe_join(base, "link", "file.txt")


def _client_with_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_PASSWORD", "testpass")
    local_main = importlib.reload(importlib.import_module("apps.local.main"))
    return TestClient(local_main.create_app())


def test_health_no_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_me_requires_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    response = client.get("/me")
    assert response.status_code == 401


def test_orchestrate_returns_intent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    login = client.post("/login", json={"username": "admin", "password": "testpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/orchestrate", json={"utterance": "hello"}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["action"] == "noop"
    assert "Phase 1" in payload["message"]
