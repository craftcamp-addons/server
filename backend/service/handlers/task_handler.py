import logging
import re
from datetime import datetime

from nats.aio.client import Client
from nats.aio.msg import Msg
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload

import utils
from backend.database import get_session, User, Task
from backend.service.handlers import BaseHandler
from database import Number


class TaskBatch(BaseModel):
    task_name: str
    batch: tuple


class NumberTask(BaseModel):
    id: int  # server_id
    number: str


class TaskHandler(BaseHandler):
    nc: Client
    regex: re.Pattern = re.compile(r"(\+?)[1-9][0-9]{7,14}")

    def __init__(self, logger: logging.Logger):
        super().__init__(logger, "task")

    async def handle(self, msg: Msg):
        init_message: TaskBatch | None = utils.unpack_msg(msg, TaskBatch)
        if init_message is None:
            self.logger.error(f"Не удалось распарсить задачу {init_message}")
            return

        async with get_session() as session:
            task: Task = (
                await session.execute(select(Task).where(Task.name == init_message.task_name))
            ).scalar_one_or_none()
            if task is None:
                task = Task(name=init_message.task_name, created_at=datetime.now())
                session.add(task)
                await session.commit()
                await session.refresh(task)

            users: list[User] = (
                await session.execute(select(User).options(joinedload(User.numbers)))
            ).unique().scalars().all()
            if len(users) == 0:
                self.logger.error(f"Пользователей нет")
                return

            for number in init_message.batch:
                user = sorted((
                                  await session.execute(select(User).options(joinedload(User.numbers)))
                              ).unique().scalars().all(), key=lambda u: len(u.numbers))[0]
                number_model: Number = (await session.scalar(
                    insert(Number).values(number=number, task_id=task.id, user_id=user.id).on_conflict_do_nothing(
                        index_elements=[Number.number]).returning(Number),
                    execution_options={"populate_existing": True}))
                if number_model is None:
                    continue
                await session.commit()
                await session.refresh(task)
                await session.refresh(user)
                await session.refresh(number_model)
