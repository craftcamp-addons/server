import logging
from abc import ABC, abstractmethod

from dynaconf import ValidationError
from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.js.api import StreamInfo


class BaseHandler(ABC):
    nc: Client
    subject: str
    logger: logging.Logger

    def __init__(self, logger: logging.Logger, stream_name: str):
        self.logger = logger
        self.subject = f"server.{stream_name}"

    async def init_stream(self, nc: Client, stream_name: str):
        try:
            try:
                stream_info: StreamInfo | None = await nc.jetstream().stream_info(stream_name)
            except Exception:
                stream_info = None
            if stream_info is None:
                await nc.jetstream().add_stream(name=stream_name,
                                                subjects=[f"{self.subject}", f"worker.{stream_name}.*"])
                stream_info: StreamInfo = await nc.jetstream().stream_info(stream_name)

            self.logger.info(f"Информация о сервере: {stream_info}")
        except Exception as e:
            self.logger.error(f"Не удалось получить информацию о сервере: {e}")

    async def subscribe(self, nc: Client):
        self.nc = nc
        await self.init_stream(self.nc, self.subject.replace("server.", ""))
        await self.nc.jetstream().subscribe(
            subject=self.subject,
            durable=self.subject.replace(".", "_"),
            cb=self.handle_message
        )

    @abstractmethod
    async def handle(self, msg: Msg):
        pass

    async def handle_message(self, msg: Msg):
        try:
            await self.handle(msg)
            await msg.ack()
        except ValidationError as e:
            self.logger.error(f"Ошибка валидации при обработке сообщения: {len(msg.data)} - {e}")
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {len(msg.data)} - {e}")
