import contextlib
from time import sleep
import random
from typing import Any, Callable

from sqlalchemy import create_engine, Engine, text, TextClause
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import settings
from backend.database.base import Base
from backend.database.user import User
from backend.database.number import NumberStatus, Number
from backend.database.task import Task


def retry(func: Callable):
    def wrap(*args, **kwargs):
        counter = 0
        while True:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                sleep((2 ** counter + random.uniform(0, 1)))
                counter += 1
                print(f"Retrying {func.__name__} {e}")

    return wrap


@retry
def _get_async_session() -> tuple[sessionmaker, AsyncEngine]:
    engine = create_async_engine(settings.database.url)

    SessionLocal = sessionmaker(autoflush=False, bind=engine, class_=AsyncSession)
    return SessionLocal, engine


async_session, engine = _get_async_session()


async def get_session_() -> AsyncSession:
    async with async_session() as session:
        yield session


@contextlib.asynccontextmanager
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


"""
select username,
(select count(status) from numbers where user_id = u.id and status = 'CREATED') as count_created,
(select count(status) from numbers where user_id = u.id and status = 'IN_WORK') as count_in_work,
(select count(status) from numbers where user_id = u.id and status = 'COMPLETED') as count_completed

from users u;
"""


async def get_users_info(session: AsyncSession, debug: bool = False) -> tuple[Any, tuple[TextClause, Any]]:
    stmt = text(
        """
        select u.id, u.username,
       (select count(status) from numbers where user_id = u.id) as count_created,
       (select count(status) from numbers where user_id = u.id and status = 'IN_WORK') as count_in_work,
       (select count(status) from numbers where user_id = u.id and status = 'COMPLETED') as count_completed

        from users u;""")
    if debug:
        return stmt, (await session.execute(stmt)).fetchall()
    else:
        return (await session.execute(stmt)).fetchall()


async def get_tasks_info(session: AsyncSession, debug: bool = False) -> tuple[Any, tuple[TextClause, Any]]:
    stmt = text("""select t.id, t.name,
       (select count(status) from numbers where task_id = t.id and status <> 'CREATED') as count_total,
       (select count(status) from numbers where task_id = t.id and status = 'COMPLETED') as count_completed
        from tasks t""")
    if debug:
        return stmt, (await session.execute(stmt)).fetchall()
    else:
        return (await session.execute(stmt)).fetchall()
