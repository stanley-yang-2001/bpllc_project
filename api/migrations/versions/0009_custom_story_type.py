"""stories may have a type of the learner's own (chat and Story Studio "Write my own")

Revision ID: 0009

0006 limited stories.story_type to the eight built-in types. A learner can now name their own ("a poem"), so the list
check becomes a length check; what may be in the label is decided by the API (tutor_core.prompts.clean_free_text), the
database only keeps it short. The downgrade turns the learners' own labels into 'story' so the old check can come back.
"""
from alembic import op

revision = "0009"
down_revision = "0008"

_BUILT_IN = "'narration','dialogue','story','diary','letter','place','routine','anecdote'"


def upgrade() -> None:
    op.execute("ALTER TABLE tutor.stories DROP CONSTRAINT stories_story_type_check")
    op.execute("ALTER TABLE tutor.stories ADD CONSTRAINT stories_story_type_check "
               "CHECK (story_type IS NULL OR char_length(story_type) BETWEEN 1 AND 40)")


def downgrade() -> None:
    op.execute(f"UPDATE tutor.stories SET story_type = 'story' WHERE story_type IS NOT NULL AND story_type NOT IN ({_BUILT_IN})")
    op.execute("ALTER TABLE tutor.stories DROP CONSTRAINT stories_story_type_check")
    op.execute(f"ALTER TABLE tutor.stories ADD CONSTRAINT stories_story_type_check CHECK (story_type IN ({_BUILT_IN}))")
