import sys

from victus.server.app import create_app
from victus.server.config import ServerSettings


def test_server_mode_does_not_import_os_bridge(tmp_path) -> None:
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
    create_app(settings)
    legacy_modules = [name for name in sys.modules if name.startswith("victus.legacy.os_bridge")]
    assert legacy_modules == []
