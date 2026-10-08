from alembic import context
from sqlalchemy import create_engine, text

config = context.config
SCHEMA = "tutor"


def _sa_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def _include_object(obj, name, type_, reflected, compare_to):
    # Langflow's own tables live in `public`; migrations must never touch them.
    return getattr(obj, "schema", SCHEMA) == SCHEMA if type_ == "table" else True


engine = create_engine(_sa_url(config.attributes["database_url"]))
with engine.connect() as connection:
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    connection.commit()
    context.configure(connection=connection, target_metadata=None, version_table_schema=SCHEMA,
                      include_schemas=True, include_object=_include_object)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
