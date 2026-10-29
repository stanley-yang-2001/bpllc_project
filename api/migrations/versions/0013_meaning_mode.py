"""the language tutor-written meanings are written in (a preference): the learner's own language, the study language, or both

Revision ID: 0013
"""
from alembic import op

revision = "0013"
down_revision = "0012"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.user_preferences ADD COLUMN meaning_mode TEXT NOT NULL DEFAULT 'native' "
               "CHECK (meaning_mode IN ('native', 'study', 'both'))")


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.user_preferences DROP COLUMN meaning_mode")
