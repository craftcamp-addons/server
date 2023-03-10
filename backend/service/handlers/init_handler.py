import logging
from typing import Optional

import nats.js.errors
from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel
from sqlalchemy import select

import utils
from backend.database import get_session, User
from backend.service.handlers.base import BaseHandler


class InitMessage(BaseModel):
    id: Optional[int]
    username: str


class InitHandler(BaseHandler):
    def __init__(self, logger: logging.Logger):
        super().__init__(logger, "init")

    async def subscribe(self, nc: Client):
        self.nc = nc
        await self.nc.subscribe(
            subject=self.subject,
            cb=self.handle_message
        )

    async def handle(self, msg: Msg):
        init_message: InitMessage | None = utils.unpack_msg(msg, InitMessage)
        if init_message is None:
            return

        self.logger.info(f"Подключение нового пользователя: {init_message}")
        kv = await self.nc.jetstream().create_key_value(bucket="connected_users")

        async with get_session() as session:
            user: User | None = (
                await session.execute(select(User).where(User.username == init_message.username))).scalar_one_or_none()
            if user is None:
                self.logger.error(f"Не удалось найти пользователя: {init_message.username}")
                user = User(username=init_message.username)
                session.add(user)
                await session.commit()
                await session.refresh(user)

        try:
            connection_state = await kv.get(f"{user.id}")
            await kv.put(key=user.id, value=b'connected')
        except nats.js.errors.KeyNotFoundError:
            await kv.create(f"{user.id}", value=b'connected')

        await self.nc.publish(subject=msg.reply,
                              payload=utils.pack_msg(InitMessage(id=user.id, username=user.username)))
        self.logger.info(f"Пользователь {user.id}:{user.username} инициализирован и подключен")
