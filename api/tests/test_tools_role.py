"""Migration 0008: the Langflow tools connect as `tutor_tools`, a role that can read and add words and nothing else.

These tests log in AS that role, so they prove what it can and cannot do rather than what a migration file says. Every test
that turns login on puts the role back to NOLOGIN afterwards (the `tools_login` fixture), so the shared test database is left
as the migrations made it."""
import re
from pathlib import Path

import psycopg2
import pytest
import yaml
from alembic import command
from alembic.config import Config
from psycopg2 import errors
from psycopg2 import sql as psql

from app.config import ConfigError, Settings, load_settings
from app.main import create_app
from app.migrate import ROOT, TOOLS_ROLE, set_tools_password
from conftest import DB_URL

from tutor_core import tools

REPO = ROOT.parent
PASSWORD = "toolsPw123"


def tools_url(password=PASSWORD):
    base = psycopg2.extensions.parse_dsn(DB_URL)
    return f"postgresql://{TOOLS_ROLE}:{password}@{base.get('host', 'localhost')}:{base.get('port', '5432')}/{base['dbname']}"


@pytest.fixture
def tools_login():
    set_tools_password(DB_URL, PASSWORD)
    yield lambda: psycopg2.connect(tools_url())
    set_tools_password(DB_URL, "")


def one(conn, query, args=None):
    with conn.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchone()


def refused(connect, statement, args=None):
    """True if the statement is refused for lack of privilege (and the connection is left usable)."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(statement, args)
            except errors.InsufficientPrivilege:
                return True
            return False
    finally:
        conn.rollback()
        conn.close()


# --- the role itself ------------------------------------------------------------------------------------------------------

def test_the_role_has_no_login_and_no_extra_powers_by_default(conn):
    row = one(conn, "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication, rolbypassrls, rolpassword IS NULL "
                    "FROM pg_authid WHERE rolname = %s", (TOOLS_ROLE,))
    assert row == (False, False, False, False, False, False, False, True)


def test_the_role_belongs_to_no_other_role(conn):
    assert one(conn, "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member WHERE r.rolname = %s", (TOOLS_ROLE,))[0] == 0


def test_a_password_turns_login_on_and_an_empty_one_turns_it_off(conn):
    try:
        set_tools_password(DB_URL, PASSWORD)
        psycopg2.connect(tools_url()).close()
        with pytest.raises(psycopg2.OperationalError):
            psycopg2.connect(tools_url("wrong"))
        set_tools_password(DB_URL, "")
        with pytest.raises(psycopg2.OperationalError):
            psycopg2.connect(tools_url())
    finally:
        set_tools_password(DB_URL, "")


def test_a_password_with_a_quote_in_it_is_stored_as_typed(conn):
    # nothing in the password is treated as SQL; ' and " and \ are only refused by config (URL safety), not by the database
    try:
        set_tools_password(DB_URL, "it's\"a\\pw;DROP")
        c = psycopg2.connect(host="localhost", dbname=psycopg2.extensions.parse_dsn(DB_URL)["dbname"], user=TOOLS_ROLE, password="it's\"a\\pw;DROP")
        c.close()
    finally:
        set_tools_password(DB_URL, "")


# --- exactly what it may do -----------------------------------------------------------------------------------------------

def table_privileges(conn, table):
    with conn.cursor() as cur:
        cur.execute("SELECT privilege_type FROM information_schema.role_table_grants WHERE grantee = %s AND table_schema = 'tutor' "
                    "AND table_name = %s", (TOOLS_ROLE, table))
        return sorted(r[0] for r in cur.fetchall())


def test_the_privilege_list_is_exactly_this(conn):
    assert table_privileges(conn, "words") == ["INSERT", "SELECT"]
    assert table_privileges(conn, "user_languages") == ["INSERT"]


def test_no_other_table_in_the_schema_is_granted_to_it(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT table_name FROM information_schema.role_table_grants WHERE grantee = %s AND table_schema = 'tutor'", (TOOLS_ROLE,))
        assert sorted(r[0] for r in cur.fetchall()) == ["user_languages", "words"]
        cur.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'tutor' AND c.relkind IN ('r', 'p') "
                    "AND NOT has_table_privilege(%s, c.oid, 'SELECT') AND NOT has_table_privilege(%s, c.oid, 'INSERT')", (TOOLS_ROLE, TOOLS_ROLE))
        denied = {r[0] for r in cur.fetchall()}
    assert {"users", "sessions", "stories", "chat_sessions", "user_preferences", "alembic_version"} <= denied


def test_it_can_add_and_read_words_and_note_the_language_through_the_real_tool(tools_login, conn, make_learner):
    learner = make_learner()
    msg = tools.add_word_for_agent("hola", learner, "es", connect=tools_login)
    assert msg == "Added 'hola' to your Spanish vocabulary."
    assert tools.add_word_for_agent("hola", learner, "es", connect=tools_login).startswith("'hola' is already")
    with conn.cursor() as cur:
        cur.execute("SELECT word FROM tutor.words WHERE user_id = %s", (learner,))
        assert [r[0] for r in cur.fetchall()] == ["hola"]
        cur.execute("SELECT language FROM tutor.user_languages WHERE user_id = %s", (learner,))
        assert [r[0] for r in cur.fetchall()] == ["es"]
    assert "hola" in tools.vocabulary_for_agent(learner, "es", connect=tools_login)


def test_it_cannot_read_accounts_or_anything_else(tools_login):
    for table in ("users", "sessions", "stories", "chat_sessions", "user_preferences", "user_languages", "alembic_version"):
        assert refused(tools_login, psql.SQL("SELECT * FROM tutor.{}").format(psql.Identifier(table))), table


def test_it_cannot_change_or_delete_words_or_make_anything(tools_login):
    assert refused(tools_login, "UPDATE tutor.words SET word = 'x'")
    assert refused(tools_login, "DELETE FROM tutor.words")
    assert refused(tools_login, "TRUNCATE tutor.words")
    assert refused(tools_login, "UPDATE tutor.user_languages SET language = 'fr'")
    assert refused(tools_login, "INSERT INTO tutor.users (email, password_hash, display_name) VALUES ('a@b.c', 'x', 'x')")
    assert refused(tools_login, "CREATE TABLE tutor.evil (id int)")
    assert refused(tools_login, "SELECT nextval('tutor.users_id_seq')")


def test_a_table_added_later_is_not_readable_until_a_migration_grants_it(conn, tools_login):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE tutor.future_table (id int)")
    conn.commit()
    try:
        assert refused(tools_login, "SELECT * FROM tutor.future_table")
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE tutor.future_table")
        conn.commit()


# --- the migration itself -------------------------------------------------------------------------------------------------

def cfg():
    c = Config(str(ROOT / "alembic.ini"))
    c.set_main_option("script_location", str(ROOT / "migrations"))
    c.attributes["database_url"] = DB_URL
    return c


def role_exists(conn):
    return one(conn, "SELECT count(*) FROM pg_roles WHERE rolname = %s", (TOOLS_ROLE,))[0] == 1


def test_downgrade_removes_the_role_and_upgrade_brings_it_back_with_the_same_grants(conn):
    try:
        command.downgrade(cfg(), "0007")
        conn.rollback()
        assert not role_exists(conn)
    finally:
        command.upgrade(cfg(), "head")
    conn.rollback()
    assert role_exists(conn)
    assert table_privileges(conn, "words") == ["INSERT", "SELECT"]
    assert table_privileges(conn, "user_languages") == ["INSERT"]


def test_upgrading_when_the_role_already_exists_is_harmless(conn):
    # the situation after a DROP SCHEMA (the test suite does one): the role outlives the schema
    try:
        command.downgrade(cfg(), "0007")
        with conn.cursor() as cur:
            cur.execute("CREATE ROLE tutor_tools LOGIN INHERIT CREATEDB")      # a hand-made role with too much
        conn.commit()
    finally:
        command.upgrade(cfg(), "head")
    conn.rollback()
    assert table_privileges(conn, "words") == ["INSERT", "SELECT"]
    assert one(conn, "SELECT rolcanlogin, rolcreatedb, rolinherit FROM pg_authid WHERE rolname = %s", (TOOLS_ROLE,)) == (False, False, False)


# --- configuration ---------------------------------------------------------------------------------------------------------

def settings(**kw):
    return Settings(database_url="postgresql://x", jwt_secret="x" * 40, **kw)


@pytest.mark.parametrize("password", ["", "abc123", "Long-Password_with.dots+and=signs!"])
def test_ordinary_passwords_pass_validation(password):
    assert settings(tools_db_password=password).validate().tools_db_password == password


@pytest.mark.parametrize("bad", [":", "@", "/", "%", "?", "#", " ", "a b", "tab\t", "new\nline", "nul\x00"])
def test_characters_that_would_break_the_database_url_are_refused(bad):
    with pytest.raises(ConfigError, match="TOOLS_DB_PASSWORD"):
        settings(tools_db_password="pw" + bad + "pw").validate()


def test_the_password_is_read_from_the_environment():
    env = {"DATABASE_URL": "postgresql://x", "JWT_SECRET": "y" * 40, "TOOLS_DB_PASSWORD": "fromenv"}
    assert load_settings(env).tools_db_password == "fromenv"
    del env["TOOLS_DB_PASSWORD"]
    assert load_settings(env).tools_db_password == ""


def test_starting_the_api_sets_the_password_and_an_empty_one_turns_login_off():
    from fastapi.testclient import TestClient
    try:
        with TestClient(create_app(Settings(database_url=DB_URL, jwt_secret="x" * 40, bcrypt_rounds=4, tools_db_password=PASSWORD))):
            psycopg2.connect(tools_url()).close()
        with TestClient(create_app(Settings(database_url=DB_URL, jwt_secret="x" * 40, bcrypt_rounds=4, tools_db_password=""))):
            with pytest.raises(psycopg2.OperationalError):
                psycopg2.connect(tools_url())
    finally:
        set_tools_password(DB_URL, "")


# --- docker-compose.yml and .env.example ------------------------------------------------------------------------------------

def compose():
    return yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def env_of(service):
    e = service["environment"]
    return dict(item.split("=", 1) for item in e) if isinstance(e, list) else e


def test_langflow_connects_to_the_database_as_the_tools_role_and_both_services_insist_on_the_password():
    services = compose()
    url = env_of(services["langflow"])["DATABASE_URL"]
    assert url.startswith(f"postgresql://{TOOLS_ROLE}:${{TOOLS_DB_PASSWORD:?")
    assert env_of(services["api"])["TOOLS_DB_PASSWORD"].startswith("${TOOLS_DB_PASSWORD:?")


def test_langflow_keeps_an_admin_connection_for_the_checking_scripts_and_not_as_its_own_database():
    services = compose()
    e = env_of(services["langflow"])
    assert e["ADMIN_DATABASE_URL"].startswith("postgresql://langflow:")
    # Langflow's own metadata still lives in the langflow account's database setting, not in the narrow role
    assert TOOLS_ROLE not in e.get("LANGFLOW_DATABASE_URL", "")


def test_the_example_env_file_documents_the_password():
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^TOOLS_DB_PASSWORD=", text, re.M)
