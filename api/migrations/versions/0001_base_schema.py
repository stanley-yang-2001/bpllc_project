"""users, user_languages, words

Revision ID: 0001
"""
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.users (
        id             SERIAL PRIMARY KEY,
        username       TEXT NOT NULL UNIQUE CHECK (username = lower(username)),
        password_hash  TEXT NOT NULL,
        display_name   TEXT NOT NULL,
        native_language TEXT NOT NULL DEFAULT 'en' CHECK (native_language ~ '^[a-z]{2}$'),
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("""
    CREATE TABLE tutor.user_languages (
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        language   TEXT NOT NULL CHECK (language ~ '^[a-z]{2}$'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, language)
    )""")
    op.execute("""
    CREATE TABLE tutor.words (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        language   TEXT NOT NULL CHECK (language ~ '^[a-z]{2}$'),
        word       TEXT NOT NULL,
        meaning    TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (user_id, language, word)
    )""")
    op.execute("CREATE INDEX words_user_lang_id ON tutor.words (user_id, language, id)")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.words, tutor.user_languages, tutor.users")
