"""The admin connection is for the checking scripts only; the tools must stay on the narrow role's connection."""
from pathlib import Path

import pytest

from tutor_core import db
ConfigError = db.ConfigError

PKG = Path(db.__file__).parent
TOOLS_URL = "postgresql://tutor_tools:pw@postgres:5432/langflow"
ADMIN_URL = "postgresql://langflow:pw@postgres:5432/langflow"


def test_admin_url_is_preferred_when_set():
    assert db.admin_database_url({"DATABASE_URL": TOOLS_URL, "ADMIN_DATABASE_URL": ADMIN_URL}) == ADMIN_URL


@pytest.mark.parametrize("admin", [None, "", "   "])
def test_without_an_admin_url_it_falls_back_to_database_url(admin):
    env = {"DATABASE_URL": TOOLS_URL}
    if admin is not None:
        env["ADMIN_DATABASE_URL"] = admin
    assert db.admin_database_url(env) == TOOLS_URL


def test_with_neither_it_says_what_to_set():
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        db.admin_database_url({})


def test_the_tools_connection_ignores_the_admin_url():
    assert db.database_url({"DATABASE_URL": TOOLS_URL, "ADMIN_DATABASE_URL": ADMIN_URL}) == TOOLS_URL


@pytest.mark.parametrize("name", ["tools.py", "vocab.py", "story.py", "words.py", "quality.py", "prompts.py"])
def test_the_tool_code_never_reaches_for_the_admin_connection(name):
    path = PKG / name
    if path.exists():
        text = path.read_text(encoding="utf-8")
        assert "connect_admin" not in text and "ADMIN_DATABASE_URL" not in text and "admin_database_url" not in text
