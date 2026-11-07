"""the example bank: at most two best-scoring example stories per language (written from seed and starter-pack words, never from a learner's words)

Revision ID: 0016
"""
from alembic import op

revision = "0016"
down_revision = "0015"


def upgrade() -> None:
    op.execute("""
    CREATE TABLE tutor.story_examples (
        id            SERIAL PRIMARY KEY,
        language      TEXT NOT NULL CHECK (language ~ '^[a-z]{2}$'),
        slot          SMALLINT NOT NULL CHECK (slot IN (1, 2)),
        text          TEXT NOT NULL CHECK (length(text) > 0),
        score         NUMERIC(4,1) NOT NULL CHECK (score > 0 AND score <= 100),
        sub_scores    JSONB NOT NULL DEFAULT '{}'::jsonb,
        score_version INTEGER NOT NULL DEFAULT 1,
        story_type    TEXT,
        topic         TEXT,
        two_pass      BOOLEAN NOT NULL DEFAULT FALSE,
        provisional   BOOLEAN NOT NULL DEFAULT TRUE,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (language, slot)
    )""")
    # The story tool (role tutor_tools) only reads the bank, to show an example in the prompt; the refresh script writes it as the owner.
    op.execute("GRANT SELECT ON tutor.story_examples TO tutor_tools")


def downgrade() -> None:
    op.execute("DROP TABLE tutor.story_examples")
