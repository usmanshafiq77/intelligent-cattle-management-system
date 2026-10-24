from sqlalchemy import Connection, text


EXPECTED_DATABASE_REVISION = "b3d5f7a9c210"


def current_database_revision(connection: Connection) -> str | None:
    return connection.scalar(text("SELECT version_num FROM alembic_version"))
