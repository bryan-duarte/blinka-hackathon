import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from core.config import Settings
from core.db.engine import ASYNC_DRIVER_SCHEME
from core.logging_config import configure_logging, get_logger

SYNC_DRIVER_SCHEME = "postgresql://"
MAINTENANCE_DATABASE = "postgres"
AUDIT_EXTENSION_IS_LOADED = (
    "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pgaudit') "
    "AND EXISTS (SELECT 1 FROM pg_settings "
    "WHERE name = 'shared_preload_libraries' AND setting LIKE '%pgaudit%')"
)

logger = get_logger(__name__)


def _to_sync_dsn(dsn: str) -> str:
    return dsn.replace(ASYNC_DRIVER_SCHEME, SYNC_DRIVER_SCHEME)


def ensure_database(dsn: str) -> None:
    database_name = conninfo_to_dict(dsn)["dbname"]
    maintenance_dsn = make_conninfo(dsn, dbname=MAINTENANCE_DATABASE)
    with psycopg.connect(maintenance_dsn, autocommit=True) as connection:
        existing_database = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if existing_database is not None:
            return
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    logger.info("database_created", database=database_name)


def ensure_audit_extension(dsn: str) -> None:
    database_name = conninfo_to_dict(dsn)["dbname"]
    with psycopg.connect(dsn, autocommit=True) as connection:
        is_audit_loaded = connection.execute(AUDIT_EXTENSION_IS_LOADED).fetchone()[0]
        if not is_audit_loaded:
            logger.info("audit_extension_skipped", database=database_name)
            return
        connection.execute("CREATE EXTENSION IF NOT EXISTS pgaudit")
    logger.info("audit_extension_ready", database=database_name)


def ensure_databases(dsns: list[str]) -> None:
    for dsn in dsns:
        sync_dsn = _to_sync_dsn(dsn)
        ensure_database(sync_dsn)
        ensure_audit_extension(sync_dsn)


if __name__ == "__main__":
    settings = Settings()
    configure_logging(settings.log_format)
    ensure_databases([settings.product_database_url, settings.agent_database_url])
