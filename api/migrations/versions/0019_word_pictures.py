"""word_pictures: one picture per word, an emoji or the learner's own photo

Revision ID: 0019
"""
from alembic import op

revision = "0019"
down_revision = "0018"


def upgrade() -> None:
    # The photo is kept in the database, next to the word it belongs to, so a backup, "Download my data" and deleting a word or an
    # account cover it with no file store to keep in step. It is small by construction (see services/pictures.py): about 30 KB.
    op.execute("""
    CREATE TABLE tutor.word_pictures (
        word_id    INTEGER PRIMARY KEY REFERENCES tutor.words(id) ON DELETE CASCADE,
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        kind       TEXT NOT NULL CHECK (kind IN ('emoji', 'photo')),
        emoji      TEXT CHECK (emoji IS NULL OR char_length(emoji) BETWEEN 1 AND 32),
        image      BYTEA,
        thumb      BYTEA,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK ((kind = 'emoji' AND emoji IS NOT NULL AND image IS NULL AND thumb IS NULL)
            OR (kind = 'photo' AND emoji IS NULL AND image IS NOT NULL AND thumb IS NOT NULL))
    )""")
    op.execute("CREATE INDEX word_pictures_user ON tutor.word_pictures (user_id, kind)")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.word_pictures")
