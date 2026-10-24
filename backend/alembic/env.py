
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.migration_config import get_migration_settings
from app.db.base import Base

# Import all models so Alembic can detect tables
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_migration_settings()

target_metadata = Base.metadata


def get_database_url():
    from sqlalchemy import URL

    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=settings.DB_NAME,
    )


def run_migrations_offline():
    url = get_database_url()

    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(
            connection=supplied_connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    database_url = get_database_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url.render_as_string(
        hide_password=False
    )
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        actual_database = connection.scalar(text("SELECT current_database()"))
        if actual_database != settings.DB_NAME:
            raise RuntimeError(
                "Alembic connected to an unexpected database; migration stopped"
            )
        connection.exec_driver_sql(
            f'SET search_path TO "{settings.DB_SCHEMA}"'
        )
        actual_schema = connection.scalar(text("SELECT current_schema()"))
        if actual_schema != settings.DB_SCHEMA:
            raise RuntimeError(
                "Alembic connected to an unexpected schema; migration stopped"
            )
        # SQLAlchemy 2 starts a transaction for SET/SELECT. Finish that
        # validation transaction before Alembic opens its transactional-DDL
        # scope; otherwise closing the outer connection rolls upgrades back.
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
