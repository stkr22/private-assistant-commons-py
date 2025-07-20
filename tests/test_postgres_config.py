import pytest

from private_assistant_commons.skill_config import PostgresConfig

DEFAULT_POSTGRES_PORT = 5432
CUSTOM_POSTGRES_PORT = 1234
ENV_POSTGRES_PORT = 5678


def test_default_values():
    config = PostgresConfig()
    assert config.user == "postgres"
    assert config.password == "postgres"
    assert config.host == "localhost"
    assert config.port == DEFAULT_POSTGRES_PORT
    assert config.database == "postgres"
    assert config.connection_string == "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"


def test_custom_values():
    config = PostgresConfig(
        user="custom_user",
        password="custom_password",
        host="custom_host",
        port=CUSTOM_POSTGRES_PORT,
        database="custom_database",
    )
    assert config.user == "custom_user"
    assert config.password == "custom_password"
    assert config.host == "custom_host"
    assert config.port == CUSTOM_POSTGRES_PORT
    assert config.database == "custom_database"
    assert (
        config.connection_string == "postgresql+psycopg://custom_user:custom_password@custom_host:1234/custom_database"
    )


def test_from_env(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "env_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env_password")
    monkeypatch.setenv("POSTGRES_HOST", "env_host")
    monkeypatch.setenv("POSTGRES_PORT", str(ENV_POSTGRES_PORT))
    monkeypatch.setenv("POSTGRES_DB", "env_database")

    config = PostgresConfig.from_env()
    assert config.user == "env_user"
    assert config.password == "env_password"
    assert config.host == "env_host"
    assert config.port == ENV_POSTGRES_PORT
    assert config.database == "env_database"
    assert config.connection_string == "postgresql+psycopg://env_user:env_password@env_host:5678/env_database"


def test_from_env_with_defaults(monkeypatch):
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_PORT", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    config = PostgresConfig.from_env()
    assert config.user == "postgres"
    assert config.password == "postgres"
    assert config.host == "localhost"
    assert config.port == DEFAULT_POSTGRES_PORT
    assert config.database == "postgres"
    assert config.connection_string == "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"


def test_invalid_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_PORT", "invalid_port")
    with pytest.raises(ValueError):
        PostgresConfig.from_env()
