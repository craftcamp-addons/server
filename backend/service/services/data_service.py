import asyncio
import logging

from nats.aio.client import Client
from nats.aio.msg import Msg
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

import utils
from backend.config import settings
from backend.database import get_session, Number, NumberStatus, User
from backend.service.handlers.task_handler import NumberTask


class DataService:
    nc: Client
    logger: logging.Logger

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def send_numbers(self, user: User, session: AsyncSession):
        subject = f"worker.data.{user.id}"
        numbers: list[Number] = (await session.execute(
            select(Number).where(
                and_(Number.status == NumberStatus.CREATED, Number.user_id == user.id)))).scalars().all()
        if len(numbers) == 0:
            return

        # self.logger.debug(f"Отправляю {len(numbers)} номеров пользователю {user.username}")
        for number in numbers:
            resp: Msg = await self.nc.request(subject=subject,
                                              payload=utils.pack_msg(NumberTask(id=number.id, number=number.number)),
                                              timeout=10)
            self.logger.debug(resp)
            number.status = NumberStatus.IN_WORK

    async def poll(self, nc: Client | None):
        while True:
            try:
                self.nc = nc
                kv = await self.nc.jetstream().create_key_value(bucket="connected_users")
                async with get_session() as session:
                    users: list[User] = (await session.execute(select(User))).scalars().all()

                    await asyncio.gather(
                        *[self.send_numbers(user, session) for user in users if
                          (await kv.get(user.id)).value == b'connected']
                    )
                    await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await asyncio.sleep(settings.service.server.data_send_interval)
