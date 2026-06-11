from __future__ import annotations

import pytest

from app import create_app


def test_create_app_requires_secret_key_for_persistent_deploy(monkeypatch):
    """Production deployments must set SECRET_KEY explicitly."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("REQUIRE_SECRET_KEY", "1")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"DEBUG": False})


def test_create_app_allows_missing_secret_key_in_testing(monkeypatch):
    """Test and dev configs may omit SECRET_KEY."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    app = create_app(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        }
    )

    assert app.config["TESTING"] is True
