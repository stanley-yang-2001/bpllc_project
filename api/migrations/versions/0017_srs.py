"""spaced repetition: each word's schedule (phase, step, ease, rest, lapses) and a log of every answer with how long it took

Revision ID: 0017
"""
from alembic import op

revision = "0017"
down_revision = "0016"


def upgrade() -> None:
    op.execute("""
    ALTER TABLE tutor.word_progress
        ADD COLUMN phase         TEXT NOT NULL DEFAULT 'learning' CHECK (phase IN ('learning', 'review', 'relearning')),
        ADD COLUMN step          SMALLINT NOT NULL DEFAULT 0 CHECK (step >= 0),
        ADD COLUMN ease          REAL NOT NULL DEFAULT 2.5 CHECK (ease BETWEEN 1.3 AND 3.5),
        ADD COLUMN interval_days REAL NOT NULL DEFAULT 0 CHECK (interval_days >= 0),
        ADD COLUMN lapses        INTEGER NOT NULL DEFAULT 0 CHECK (lapses >= 0),
        ADD COLUMN last_grade    SMALLINT CHECK (last_grade BETWEEN 1 AND 4)
    """)
    # words already practised keep what the five boxes told us: box 2 and up were resting (1, 3, 7 or 21 days), box 1 is still learning
    op.execute("""
    UPDATE tutor.word_progress SET
        phase = CASE WHEN box >= 2 THEN 'review' ELSE 'learning' END,
        interval_days = CASE box WHEN 2 THEN 1 WHEN 3 THEN 3 WHEN 4 THEN 7 WHEN 5 THEN 21 ELSE 0 END
    """)
    op.execute("""
    CREATE TABLE tutor.review_log (
        id             BIGSERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        word_id        INTEGER NOT NULL REFERENCES tutor.words(id) ON DELETE CASCADE,
        reviewed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        mode           TEXT NOT NULL DEFAULT 'flashcards',
        direction      TEXT,
        grade          SMALLINT NOT NULL CHECK (grade BETWEEN 1 AND 4),
        think_ms       INTEGER CHECK (think_ms >= 0),
        rate_ms        INTEGER CHECK (rate_ms >= 0),
        phase_before   TEXT NOT NULL,
        was_due        BOOLEAN NOT NULL,
        counted        BOOLEAN NOT NULL,
        ease_after     REAL NOT NULL,
        delay_seconds  INTEGER NOT NULL CHECK (delay_seconds >= 0)
    )""")
    op.execute("CREATE INDEX review_log_user_time ON tutor.review_log (user_id, reviewed_at DESC)")
    op.execute("CREATE INDEX review_log_word ON tutor.review_log (word_id, reviewed_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.review_log")
    op.execute("ALTER TABLE tutor.word_progress DROP COLUMN last_grade, DROP COLUMN lapses, DROP COLUMN interval_days, "
               "DROP COLUMN ease, DROP COLUMN step, DROP COLUMN phase")
