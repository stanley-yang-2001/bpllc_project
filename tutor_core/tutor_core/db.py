"""Database connection, from the environment only. No credentials, host names or database names live in this package."""
from __future__ import annotations

import os

import psycopg2


class ConfigError(RuntimeError):
    """A required environment variable is missing."""


def database_url(env=None) -> str:
    env = os.environ if env is None else env
    url = (env.get("DATABASE_URL") or "").strip()
    if not url:
        raise ConfigError("DATABASE_URL is not set. Set it in the environment of whatever runs tutor_core "
                          "(the api and langflow services in docker-compose.yml).")
    return url


def connect(env=None):
    return psycopg2.connect(database_url(env))
