"""saved stories (the library)

Revision ID: 0006
"""
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.stories (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        language   TEXT NOT NULL CHECK (language ~ '^[a-z]{2}$'),
        story_type TEXT CHECK (story_type IN ('narration','dialogue','story','diary','letter','place','routine','anecdote')),
        topic      TEXT CHECK (topic IS NULL OR char_length(topic) <= 120),
        body       TEXT NOT NULL CHECK (char_length(btrim(body)) > 0 AND char_length(body) <= 20000),
        passed     BOOLEAN NOT NULL,
        report     JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX stories_user_language ON tutor.stories (user_id, language, id DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.stories")
