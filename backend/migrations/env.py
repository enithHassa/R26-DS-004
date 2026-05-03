import importlib
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.shared.config.database import Base
from backend.shared.config.settings import settings


def _register_component_models() -> None:
    """Import every component's ``app.models`` package so its tables register
    on ``Base.metadata``.

    Each component uses its own ``app/`` package. We load them one at a time,
    putting that component's directory at the front of ``sys.path`` while we
    import, then purging ``app.*`` from ``sys.modules`` so the next component
    can load its own ``app`` cleanly.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    for comp_dir in sorted(backend_dir.glob("comp-*")):
        models_init = comp_dir / "app" / "models" / "__init__.py"
        if not models_init.exists():
            continue
        sys.path.insert(0, str(comp_dir))
        try:
            importlib.import_module("app.models")
        finally:
            sys.path.pop(0)
            for key in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
                del sys.modules[key]


_register_component_models()

config = context.config
# Let callers override the URL (tests, CI, offline sqlite runs); otherwise
# use the shared settings. Escape '%' for configparser interpolation (passwords
# with special chars get URL-encoded, e.g. '@' -> '%40').
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
