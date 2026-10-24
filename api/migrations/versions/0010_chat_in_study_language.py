"""chat replies in the study language (a display preference)

Revision ID: 0010
"""
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.user_preferences ADD COLUMN chat_in_study_language BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.user_preferences DROP COLUMN chat_in_study_language")
