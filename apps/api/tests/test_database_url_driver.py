"""Regression tests for the SQLAlchemy driver marker in DATABASE_URL.

The project depends on psycopg 3, not psycopg2. A "postgresql://" URL
carries no driver marker, so SQLAlchemy reaches for psycopg2 and raises
ModuleNotFoundError while creating the engine. Because the engine is built
at import time, that kills the app before it serves anything, and it
happens on the first boot in a real environment rather than in tests where
DATABASE_URL is usually a local SQLite file.

Both schemas below are exercised because they failed independently: the
application engine and the Alembic env module.
"""

from app.core.config import Settings


def _url(scheme: str) -> str:
    return f"{scheme}://user:pass@host.example.com:5432/dbname"


def test_plain_postgresql_url_gets_psycopg_driver() -> None:
    settings = Settings(DATABASE_URL=_url("postgresql"))
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_postgres_alias_gets_psycopg_driver() -> None:
    settings = Settings(DATABASE_URL=_url("postgres"))
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_existing_driver_marker_is_preserved() -> None:
    settings = Settings(DATABASE_URL=_url("postgresql+psycopg"))
    assert settings.sqlalchemy_database_url == _url("postgresql+psycopg")


def test_alternate_driver_is_not_overwritten() -> None:
    # An explicit choice by the deployer must survive normalisation.
    settings = Settings(DATABASE_URL=_url("postgresql+psycopg2"))
    assert settings.sqlalchemy_database_url == _url("postgresql+psycopg2")


def test_query_parameters_are_preserved() -> None:
    # Neon and Supabase both append options such as sslmode and channel_binding.
    # Dropping them turns a working URL into a connection failure.
    settings = Settings(
        DATABASE_URL=_url("postgresql") + "?sslmode=require&channel_binding=require"
    )
    result = settings.sqlalchemy_database_url
    assert result.startswith("postgresql+psycopg://")
    assert "sslmode=require" in result
    assert "channel_binding=require" in result


def test_non_postgres_url_is_left_alone() -> None:
    settings = Settings(DATABASE_URL="sqlite:///./test.db")
    assert settings.sqlalchemy_database_url == "sqlite:///./test.db"


def test_empty_url_stays_empty() -> None:
    assert Settings(DATABASE_URL="").sqlalchemy_database_url == ""


def test_credentials_are_not_altered() -> None:
    # A password containing a scheme-like prefix must not be rewritten.
    settings = Settings(DATABASE_URL="postgresql://u:postgres:x@h:5432/db")
    assert ":postgres:x@" in settings.sqlalchemy_database_url
