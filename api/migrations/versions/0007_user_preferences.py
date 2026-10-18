"""display preferences on the account (M8p)

Revision ID: 0007
"""
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    # No row means "defaults". The row is created on the first save. user_id is the primary key, so the guard tests
    # (export contains it, deletion removes it) apply to this table by themselves.
    op.execute("""
    CREATE TABLE tutor.user_preferences (
        user_id                   INTEGER PRIMARY KEY REFERENCES tutor.users(id) ON DELETE CASCADE,
        active_language           TEXT CHECK (active_language IS NULL OR active_language ~ '^[a-z]{2}$'),
        ui_follows_study_language BOOLEAN NOT NULL DEFAULT false,
        theme                     TEXT NOT NULL DEFAULT 'system' CHECK (theme ~ '^[a-z][a-z0-9-]{0,23}$'),
        custom_colors             JSONB,
        updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.user_preferences")
