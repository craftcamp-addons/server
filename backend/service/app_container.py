import asyncio
import logging

import nats
from nats.aio.client import Client
from nats.errors import NoServersError

from backend.config import settings
from service.services.data_service import DataService
from service.handlers import DataHandler, BaseHandler, InitHandler
from service.handlers.task_handler import TaskHandler
from service.services.heartbeat_service import HeartBeatService


class AppContainer:
    nc: Client
    handlers: list[BaseHandler] = []
    heartbeat_service: HeartBeatService
    data_service: DataService
    logger: logging.Logger

    def __init__(self, logger: logging.Logger = logging.getLogger("__main__")):
        self.logger = logger
        self.handlers = [InitHandler(logging.getLogger("InitHandler")),
                         DataHandler(logging.getLogger("DataHandler")),
                         TaskHandler(logging.getLogger("TaskHandler"))
                         ]
        self.heartbeat_service = HeartBeatService(logging.getLogger("HeartBeatService"))
        self.data_service = DataService(logging.getLogger("DataService"))

    async def run(self):
        try:
            self.nc = await nats.connect(settings.service.mq_url, max_reconnect_attempts=2)
        except NoServersError as e:
            self.logger.exception(f"Не удалось подключиться к NATS: {e}", exc_info=None)
            return

        await asyncio.gather(*[handler.subscribe(self.nc) for handler in self.handlers])
        self.logger.info("Подписочка на обновления есть, запускаю сервисы")
        await asyncio.gather(
            self.heartbeat_service.poll(self.nc),
            self.data_service.poll(self.nc)
        )
