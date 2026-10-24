from sqlalchemy import Connection, text


EXPECTED_DATABASE_REVISION = "f1a3b5c7d906"


def current_database_revision(connection: Connection) -> str | None:
    return connection.scalar(text("SELECT version_num FROM alembic_version"))
