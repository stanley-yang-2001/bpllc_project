"""a part of speech for a word (noun, verb, adjective ...), chosen by the learner or written by the tutor

Revision ID: 0015
"""
from alembic import op

revision = "0015"
down_revision = "0014"


def upgrade() -> None:
    # the allowed codes depend on the language (tutor_core.pos), so the app checks them; the column only keeps them tidy
    op.execute("ALTER TABLE tutor.words ADD COLUMN pos TEXT CHECK (pos IS NULL OR pos ~ '^[a-z_]{2,20}$')")


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.words DROP COLUMN pos")
