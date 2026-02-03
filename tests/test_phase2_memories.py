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


def test_memory_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    response = client.get("/memory/list")
    assert response.status_code == 401


def test_memory_add_search_list_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    headers = _auth_headers(client)

    add_response = client.post(
        "/memory/add",
        json={"content": "Remember pizza toppings", "type": "note", "tags": ["food"]},
        headers=headers,
    )
    assert add_response.status_code == 200
    memory_id = add_response.json()["id"]

    search_response = client.get("/memory/search", params={"q": "pizza"}, headers=headers)
    assert search_response.status_code == 200
    results = search_response.json()["results"]
    assert any(item["id"] == memory_id for item in results)

    list_response = client.get("/memory/list", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["results"]
    assert any(item["id"] == memory_id for item in listed)

    delete_response = client.delete(f"/memory/{memory_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    search_after = client.get("/memory/search", params={"q": "pizza"}, headers=headers)
    assert all(item["id"] != memory_id for item in search_after.json()["results"])
