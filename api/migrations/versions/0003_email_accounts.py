"""accounts are identified by email (no separate username); record privacy-policy consent

Revision ID: 0003

Existing pre-release accounts get a placeholder address '<old username>@legacy.invalid' and no consent record.
"""
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.users ADD COLUMN email TEXT")
    op.execute("UPDATE tutor.users SET email = lower(username) || '@legacy.invalid'")
    op.execute("ALTER TABLE tutor.users ALTER COLUMN email SET NOT NULL")
    op.execute("ALTER TABLE tutor.users ADD CONSTRAINT users_email_key UNIQUE (email)")
    op.execute("ALTER TABLE tutor.users ADD CONSTRAINT users_email_lower CHECK (email = lower(email))")
    op.execute("ALTER TABLE tutor.users DROP COLUMN username")
    op.execute("ALTER TABLE tutor.users ADD COLUMN privacy_accepted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE tutor.users ADD COLUMN privacy_version TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.users DROP COLUMN privacy_version, DROP COLUMN privacy_accepted_at")
    op.execute("ALTER TABLE tutor.users ADD COLUMN username TEXT")
    op.execute("UPDATE tutor.users SET username = lower(split_part(email, '@', 1)) || id::text")
    op.execute("ALTER TABLE tutor.users ALTER COLUMN username SET NOT NULL")
    op.execute("ALTER TABLE tutor.users ADD CONSTRAINT users_username_key UNIQUE (username)")
    op.execute("ALTER TABLE tutor.users DROP CONSTRAINT users_email_lower, DROP CONSTRAINT users_email_key, DROP COLUMN email")
