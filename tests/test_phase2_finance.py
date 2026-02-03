from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.orchestrator.deterministic import parse_finance_intent


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


def test_finance_endpoints_require_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    response = client.get("/finance/list")
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("utterance", "amount", "category"),
    [
        ("spent 3 on coffee", 3.0, "coffee"),
        ("I spent $3 on coffee at Starbucks", 3.0, "coffee"),
        ("paid 12.50 for groceries", 12.5, "groceries"),
    ],
)
def test_finance_deterministic_parsing(utterance: str, amount: float, category: str) -> None:
    intent = parse_finance_intent(utterance)
    assert intent is not None
    assert intent.action == "finance.add_transaction"
    assert intent.parameters["amount"] == amount
    assert intent.parameters["category"] == category


def test_finance_add_list_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = _client_with_env(monkeypatch, tmp_path)
    headers = _auth_headers(client)
    add_response = client.post(
        "/finance/add",
        json={"amount": 3.25, "currency": "USD", "category": "coffee", "merchant": "Cafe"},
        headers=headers,
    )
    assert add_response.status_code == 200
    transaction_id = add_response.json()["id"]

    list_response = client.get("/finance/list", params={"category": "coffee"}, headers=headers)
    assert list_response.status_code == 200
    transactions = list_response.json()["results"]
    assert any(item["id"] == transaction_id for item in transactions)

    summary_response = client.get("/finance/summary", params={"period": "week"}, headers=headers)
    assert summary_response.status_code == 200
    report = summary_response.json()["report"]
    assert report["totals"]["coffee"] >= 325
