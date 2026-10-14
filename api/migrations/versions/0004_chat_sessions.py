"""which Langflow chat sessions each learner has, so account deletion can remove them

Only ids are kept here, never message content: the messages live in Langflow.

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.chat_sessions (
        user_id    INTEGER NOT NULL REFERENCES tutor.users(id) ON DELETE CASCADE,
        session_id TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, session_id)
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.chat_sessions")
