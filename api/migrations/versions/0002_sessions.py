"""server-side sessions, so logout really revokes a login

Revision ID: 0002
"""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.sessions (
        id         TEXT PRIMARY KEY,                                   -- the token's jti
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL
    )""")
    op.execute("CREATE INDEX sessions_user ON tutor.sessions (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.sessions")
