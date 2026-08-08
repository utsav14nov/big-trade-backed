"""Alembic environment — reads DATABASE_URL from app settings, uses sync driver for migrations."""
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async():
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.connect() as conn:
        await conn.run_sync(run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=str(settings.DATABASE_URL), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async())
