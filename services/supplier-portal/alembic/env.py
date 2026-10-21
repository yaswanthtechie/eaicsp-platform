from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.database import Base
from app.models import POMirror, Supplier  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_URL.replace("%", "%%"),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
        # Keep alembic_version in the default schema,
        # consistent with online migrations.
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            if connection.dialect.name == "postgresql":
                schema = settings.SUPPLIER_DB_SCHEMA

                # Create the application schema before the migration.
                connection.exec_driver_sql(
                    f'CREATE SCHEMA IF NOT EXISTS "{schema}"'
                )
                connection.commit()

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                compare_type=True,
                # Do not set version_table_schema here:
                # Alembic tracks revisions in the default schema.
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

