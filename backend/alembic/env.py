import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

LANGGRAPH_CHECKPOINT_TABLE_PREFIX = "checkpoint"
SECTION_URL_ENV_VARS = {
    "product": "BLINKA_PRODUCT_DATABASE_URL",
    "payments": "BLINKA_PAYMENTS_DATABASE_URL",
}

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if config.config_ini_section == "payments":
    from core.db.base import PaymentsBase as target_base
else:
    import modules.auth.models  # noqa: F401
    import modules.bills.models  # noqa: F401
    import modules.files.models  # noqa: F401
    import modules.fx.models  # noqa: F401
    import modules.inbox.models  # noqa: F401
    import modules.payment_policy.models  # noqa: F401
    import modules.payments.models  # noqa: F401
    from core.db.base import ProductBase as target_base

target_metadata = target_base.metadata


def _section_url() -> str:
    url_var = SECTION_URL_ENV_VARS.get(config.config_ini_section)
    env_url = os.getenv(url_var) if url_var is not None else None
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")


def _sync_url() -> str:
    return (
        _section_url()
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


def _include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    is_langgraph_table = type_ == "table" and (name or "").startswith(
        LANGGRAPH_CHECKPOINT_TABLE_PREFIX
    )
    return not is_langgraph_table


def _version_table() -> str:
    return config.get_main_option("version_table") or "alembic_version"


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=_version_table(),
        include_name=_include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=_version_table(),
            include_name=_include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
