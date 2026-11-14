"""rewards: when a word became known, and the learner's daily goal and whether to show rewards

Revision ID: 0018
"""
from alembic import op

revision = "0018"
down_revision = "0017"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.word_progress ADD COLUMN known_at TIMESTAMPTZ")
    # words that are already in box 4 or 5 count as learned when they were last answered
    op.execute("UPDATE tutor.word_progress SET known_at = last_answered_at WHERE box >= 4")
    op.execute("""
    ALTER TABLE tutor.user_preferences
        ADD COLUMN daily_goal   SMALLINT NOT NULL DEFAULT 10 CHECK (daily_goal BETWEEN 5 AND 100),
        ADD COLUMN show_rewards BOOLEAN NOT NULL DEFAULT true
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.user_preferences DROP COLUMN show_rewards, DROP COLUMN daily_goal")
    op.execute("ALTER TABLE tutor.word_progress DROP COLUMN known_at")
