import asyncio
import logging

import asyncpg.exceptions
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.errors import NoRespondersError
from nats.js.kv import KeyValue
from pydantic import BaseModel
from sqlalchemy import select

import utils
from backend.config import settings
from database import get_session, User


class Ping(BaseModel):
    id: int


class HeartBeatService:
    logger: logging.Logger

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def heartbeat_user(self, user: User, nc: Client, kv: KeyValue):
        try:
            self.logger.debug(f"Стукаю {user.id}:{user.username}")
            res: Msg = await nc.request(subject=f"worker.heartbeat.{user.id}",
                                        payload=utils.pack_msg(
                                            Ping(id=user.id)),
                                        timeout=10)
            ping: Ping | None = utils.unpack_msg(res, Ping)
            real_state = 'connected' if ping is not None and ping.id == user.id else 'not connected'
            await kv.put(user.id, real_state.encode())
            self.logger.debug(f"Стук {user.id}:{user.username} - {real_state}")
        except Exception:
            await kv.put(f"{user.id}", b"not connected")
            self.logger.debug(f"Не стук {user.id}:{user.username} - not connected")

    async def poll(self, nc: Client | None):
        try:
            kv = await nc.jetstream().create_key_value(bucket='connected_users')

            async with get_session() as session:
                users = (await session.execute(select(User).order_by(User.id))).scalars().all()
            for user in users:
                try:
                    await kv.create(f"{user.id}", b'not connected')
                    self.logger.debug(f"Сделал запись на {user.id}")
                except Exception as e:
                    self.logger.debug(f"Не сделал запись на {user.id} - {e}")
                    continue

            while True:
                self.logger.debug("Начинаю сердцестуки 🗿🗿")
                await asyncio.gather(*[
                    self.heartbeat_user(user, nc, kv) for user in users
                ])

                await asyncio.sleep(settings.service.server.heartbeat_interval)
        except (NoRespondersError, asyncpg.exceptions.UndefinedTableError):
            self.logger.error("Никого")
        except Exception as e:
            self.logger.error(e)
