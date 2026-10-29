"""what a learner got right and wrong in practice: one row per word (its box and when it is due) and one per day practised

Revision ID: 0014
"""
from alembic import op

revision = "0014"
down_revision = "0013"


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.word_progress (
        word_id          INTEGER PRIMARY KEY REFERENCES tutor.words(id) ON DELETE CASCADE,
        user_id          INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        box              SMALLINT NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
        due_at           TIMESTAMPTZ NOT NULL,
        right_count      INTEGER NOT NULL DEFAULT 0 CHECK (right_count >= 0),
        wrong_count      INTEGER NOT NULL DEFAULT 0 CHECK (wrong_count >= 0),
        last_answered_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")
    op.execute("CREATE INDEX word_progress_user_due ON tutor.word_progress (user_id, due_at)")
    op.execute("""
    CREATE TABLE tutor.practice_days (
        user_id INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        day     DATE NOT NULL,
        answers INTEGER NOT NULL DEFAULT 0 CHECK (answers >= 0),
        PRIMARY KEY (user_id, day)
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.practice_days")
    op.execute("DROP TABLE tutor.word_progress")
