from pathlib import Path

from fastapi.testclient import TestClient

from victus.server.app import create_app
from victus.server.config import ServerSettings


def test_protected_route_requires_auth(tmp_path: Path) -> None:
    settings = ServerSettings(
        database_url=f"sqlite:///{tmp_path / 'server.db'}",
        token_secret="test-secret",
        token_ttl_seconds=3600,
        cors_allow_origins=[],
        allow_registration=True,
        mfa_secret_key="mfa-secret",
        rate_limit_per_minute=30,
        rate_limit_window_seconds=60,
        version="test",
    )
    app = create_app(settings)
    client = TestClient(app)

    register = client.post("/auth/register", json={"email": "me@example.com", "password": "password123"})
    assert register.status_code == 200

    login = client.post("/auth/login", json={"email": "me@example.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["token"]

    unauthorized = client.get("/me")
    assert unauthorized.status_code == 401

    authorized = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert authorized.status_code == 200
    assert authorized.json()["email"] == "me@example.com"
