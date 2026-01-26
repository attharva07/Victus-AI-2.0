import time

from victus.server.security import build_token_payload, create_access_token, verify_access_token


def test_token_round_trip() -> None:
    secret = "test-secret"
    payload = build_token_payload("user-123", "user@example.com", 60)
    token = create_access_token(payload, secret)
    decoded = verify_access_token(token, secret)
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "user@example.com"


def test_token_expiry() -> None:
    secret = "test-secret"
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "iat": int(time.time()) - 120,
        "exp": int(time.time()) - 60,
    }
    token = create_access_token(payload, secret)
    assert verify_access_token(token, secret) is None
