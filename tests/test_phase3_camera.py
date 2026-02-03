from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _client_with_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, enabled: bool) -> TestClient:
    monkeypatch.setenv("VICTUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("VICTUS_LOCAL_ADMIN_PASSWORD", "testpass")
    monkeypatch.setenv("VICTUS_CAMERA_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("VICTUS_CAMERA_BACKEND", "stub")
    monkeypatch.setenv("VICTUS_CAMERA_MAX_IMAGE_BYTES", "2000000")
    monkeypatch.setenv("VICTUS_CAMERA_MAX_DIM", "1280")
    local_main = importlib.reload(importlib.import_module("apps.local.main"))
    return TestClient(local_main.create_app())


def _auth_headers(client: TestClient) -> dict[str, str]:
    login = client.post("/login", json={"username": "admin", "password": "testpass"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_camera_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path, enabled=False)
    assert client.get("/camera/status").status_code == 401
    assert client.post("/camera/capture").status_code == 401
    assert client.post("/camera/recognize").status_code == 401


def test_camera_disabled_returns_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path, enabled=False)
    headers = _auth_headers(client)

    status_response = client.get("/camera/status", headers=headers)
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["enabled"] is False
    assert payload["ok"] is False

    capture_response = client.post("/camera/capture", headers=headers)
    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert capture_payload["ok"] is False
    assert capture_payload["enabled"] is False

    recognize_response = client.post("/camera/recognize", headers=headers)
    assert recognize_response.status_code == 200
    recognize_payload = recognize_response.json()
    assert recognize_payload["ok"] is False
    assert recognize_payload["enabled"] is False


def test_camera_stub_capture_and_recognize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path, enabled=True)
    headers = _auth_headers(client)

    status_response = client.get("/camera/status", headers=headers)
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["enabled"] is True
    assert status_payload["backend"] == "stub"
    assert status_payload["ok"] is True

    capture_response = client.post("/camera/capture", headers=headers)
    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert capture_payload["ok"] is True
    assert capture_payload["enabled"] is True
    assert capture_payload["backend"] == "stub"
    assert capture_payload["stored"] is False
    assert capture_payload["capture_id"]

    recognize_response = client.post("/camera/recognize", headers=headers)
    assert recognize_response.status_code == 200
    recognize_payload = recognize_response.json()
    assert recognize_payload["ok"] is True
    assert recognize_payload["enabled"] is True
    assert recognize_payload["backend"] == "stub"
    assert recognize_payload["matches"] == []
