"""a salt of our own for each password, stored beside the hash

The hash is bcrypt(base64(SHA-256(salt_bytes || password))). Accounts made before this have no salt (NULL): they
still log in with plain bcrypt and are given a salt on their next successful login.

Revision ID: 0005
"""
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.users ADD COLUMN password_salt TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE tutor.users DROP COLUMN password_salt")
