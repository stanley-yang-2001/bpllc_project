"""a least-privilege database role for the Langflow tools

Revision ID: 0008

The Langflow tools (Add Word, Story Generator Tool, Word Loader) run inside the Langflow container and used to connect
with the same account as the API, which can read and change everything. They need very little: read a learner's words,
add a word, and note that the learner now uses that language. This creates a role that can do exactly that and nothing
else, so a tool that misbehaves (a bug, a prompt that talks the Agent into something odd) cannot reach accounts, sessions,
stories, chat sessions or preferences, and cannot change or delete a word.

  tutor.words            SELECT, INSERT   (not UPDATE or DELETE)
  tutor.user_languages   INSERT           (not even SELECT)
  tutor.words_id_seq     USAGE            (the id of a new word)
  schema tutor           USAGE

The role has NO LOGIN here. The API turns login on at startup from TOOLS_DB_PASSWORD (app/migrate.py: set_tools_password);
without a password it stays off. Grants are explicit, so a table added by a later migration is NOT readable by the role
until a migration grants it.

Needs a database user that may create roles (the compose file's `langflow` user is a superuser). The role is created only
if it does not exist and its attributes are reset either way, so running this again, or after DROP SCHEMA in the tests, is safe.
"""
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tutor_tools') THEN
            CREATE ROLE tutor_tools NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;
        END IF;
    END
    $$""")
    # also for a role that was there already (made by hand, or left over): it must not keep a login or any extra power
    op.execute("ALTER ROLE tutor_tools NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS")
    op.execute("GRANT USAGE ON SCHEMA tutor TO tutor_tools")
    op.execute("GRANT SELECT, INSERT ON tutor.words TO tutor_tools")
    op.execute("GRANT INSERT ON tutor.user_languages TO tutor_tools")
    op.execute("GRANT USAGE ON SEQUENCE tutor.words_id_seq TO tutor_tools")


def downgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tutor_tools') THEN
            DROP OWNED BY tutor_tools;
            DROP ROLE tutor_tools;
        END IF;
    END
    $$""")
