from __future__ import annotations

import pytest

from eci.config import Settings
from eci.exceptions import ConfigurationError


def test_openai_backend_requires_key() -> None:
    with pytest.raises(ConfigurationError):
        Settings(_env_file=None, embedding_backend="openai", openai_api_key=None)


def test_weaviate_backend_requires_key() -> None:
    with pytest.raises(ConfigurationError):
        Settings(_env_file=None, vector_backend="weaviate", weaviate_api_key=None)


def test_production_rejects_demo_secret() -> None:
    with pytest.raises(ConfigurationError):
        Settings(_env_file=None, environment="production")


def test_database_dialect_ignores_driver_suffix() -> None:
    settings = Settings(
        _env_file=None,
        database_url="mysql+pymysql://user:pass@localhost/eci",
    )
    assert settings.database_dialect == "mysql"
