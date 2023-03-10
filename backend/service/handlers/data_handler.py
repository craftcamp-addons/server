import logging
from pathlib import Path

import logging
from pathlib import Path

import aiofiles as aiofiles
import nats.js.errors
from nats.aio.msg import Msg
from pydantic import BaseModel
from sqlalchemy import update

import utils
from backend.config import settings
from backend.database import get_session, Number, NumberStatus
from backend.service.handlers.base import BaseHandler


class NumberResult(BaseModel):
    user_id: int
    id: int  # server_id
    number: str


class DataHandler(BaseHandler):
    photos_dir: Path

    def __init__(self, logger: logging.Logger):
        super().__init__(logger, "data")
        self.photos_dir = Path(settings.service.photos_dir)
        if not self.photos_dir.exists():
            self.photos_dir.mkdir(parents=True)

    async def handle(self, msg: Msg):
        self.logger.debug(f"Прилетело сообщение: {msg.data}")
        data: NumberResult | None = utils.unpack_msg(msg, NumberResult)
        if data is None:
            return
        kv = await self.nc.jetstream().key_value("data_store")
        try:
            value = await kv.get(data.number)
            async with aiofiles.open(self.photos_dir / (data.number + '.png'), 'wb') as f:
                await f.write(value.value)
                self.logger.debug(f"Положил файл в {self.photos_dir / (data.number + '.png')}")
            await kv.delete(data.number, value.revision)
        except nats.js.errors.KeyNotFoundError:
            self.logger.error(f"Не нашёл ключ {data.number}")
            return
        async with get_session() as session:
            await session.execute(
                update(Number).where(Number.number == data.number).
                values(status=NumberStatus.COMPLETED)
            )
            await session.commit()
