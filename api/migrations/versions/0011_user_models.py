"""a learner's own model: an account switch and one saved endpoint per learner (docs/CUSTOM-MODEL-DESIGN.md)

Revision ID: 0011
"""
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    # Off for everyone: the operator switches an account on (decision 2, 24 Oct 2026).
    op.execute("ALTER TABLE tutor.users ADD COLUMN custom_model_enabled BOOLEAN NOT NULL DEFAULT false")
    # One row per learner. The key is stored encrypted (api/app/services/model_secrets.py) and never returned by any route;
    # key_last4 is all the page ever shows of it. The row goes with the account (cascade).
    op.execute("""
    CREATE TABLE tutor.user_models (
        user_id           INTEGER PRIMARY KEY REFERENCES tutor.users(id) ON DELETE CASCADE,
        model             TEXT NOT NULL CHECK (char_length(model) BETWEEN 1 AND 100),
        base_url          TEXT NOT NULL CHECK (char_length(base_url) BETWEEN 8 AND 200),
        api_key_encrypted TEXT NOT NULL DEFAULT '',
        key_last4         TEXT NOT NULL DEFAULT '' CHECK (char_length(key_last4) <= 4),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.user_models")
    op.execute("ALTER TABLE tutor.users DROP COLUMN custom_model_enabled")
