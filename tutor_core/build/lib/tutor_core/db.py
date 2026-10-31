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


ADMIN_URL_ENV = "ADMIN_DATABASE_URL"


def admin_database_url(env=None) -> str:
    """For the CHECKING SCRIPTS and their tests only (scripts/run_routing_tests.py, scripts/m3_check.py): they create and
    delete throwaway learners, which the tools' least-privilege role (migration 0008) may not. ADMIN_DATABASE_URL when it is
    set, else DATABASE_URL, so a stack without the narrow role keeps working. The tools and the story pipeline never call this
    (a test checks that); they use `connect` and so are held to whatever role DATABASE_URL names."""
    env = os.environ if env is None else env
    return (env.get(ADMIN_URL_ENV) or "").strip() or database_url(env)


def connect_admin(env=None):
    return psycopg2.connect(admin_database_url(env))
