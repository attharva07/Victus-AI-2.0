from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _client_with_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_PASSWORD", "testpass")
    local_main = importlib.reload(importlib.import_module("apps.local.main"))
    return TestClient(local_main.create_app())


def _auth_headers(client: TestClient) -> dict[str, str]:
    login = client.post("/login", json={"username": "admin", "password": "testpass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_files_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    response = client.get("/files/list")
    assert response.status_code == 401


def test_files_write_read_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    headers = _auth_headers(client)

    write_response = client.post(
        "/files/write",
        json={"path": "notes.txt", "content": "hello", "mode": "overwrite"},
        headers=headers,
    )
    assert write_response.status_code == 200

    read_response = client.get("/files/read", params={"path": "notes.txt"}, headers=headers)
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "hello"

    list_response = client.get("/files/list", headers=headers)
    assert list_response.status_code == 200
    assert "notes.txt" in list_response.json()["files"]


def test_files_sandbox_blocks_traversal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    headers = _auth_headers(client)
    response = client.post(
        "/files/write",
        json={"path": "../escape.txt", "content": "nope", "mode": "overwrite"},
        headers=headers,
    )
    assert response.status_code == 400


def test_files_sandbox_blocks_extensions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    headers = _auth_headers(client)
    response = client.post(
        "/files/write",
        json={"path": "malware.exe", "content": "nope", "mode": "overwrite"},
        headers=headers,
    )
    assert response.status_code == 400
