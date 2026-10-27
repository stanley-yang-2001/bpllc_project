"""vocabulary sets: a learner's own named groups of words (the words with no set are the General set)

Revision ID: 0012
"""
from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade() -> None:
    # A set belongs to one learner and one language (words are per language). A name is unique per learner and language,
    # ignoring case. The words of a deleted set go back to General (ON DELETE SET NULL); they are never deleted with it.
    op.execute("""
    CREATE TABLE tutor.word_sets (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        language   TEXT NOT NULL,
        name       TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 40),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE UNIQUE INDEX word_sets_name_key ON tutor.word_sets (user_id, language, lower(name))")
    op.execute("ALTER TABLE tutor.words ADD COLUMN set_id INTEGER REFERENCES tutor.word_sets(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX words_set_idx ON tutor.words (user_id, language, set_id)")


def downgrade() -> None:
    op.execute("DROP INDEX tutor.words_set_idx")
    op.execute("ALTER TABLE tutor.words DROP COLUMN set_id")
    op.execute("DROP TABLE tutor.word_sets")
