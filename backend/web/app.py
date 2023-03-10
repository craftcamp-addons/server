import logging
from itertools import groupby

import fastapi
import nats
import nats.errors
import nats.js.errors
from fastapi import Depends, UploadFile, Form, HTTPException, Body
from nats.aio.client import Client
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.background import BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket

import utils
from backend.config import settings
from backend.database import User, get_session_, get_users_info, get_tasks_info, Number, Task
from backend.log import init_logging

init_logging()
app = fastapi.FastAPI(
    debug=settings.web.debug
)

origins = [
    "http://46.138.248.205:8010",
    "http://46.138.248.205:8003"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


class TaskBatch(BaseModel):
    task_name: str
    batch: tuple


async def create_task(task_name: str, file: UploadFile):
    logger.info(f"Полетели задачки: {file.size}")
    nc = await nats.connect(settings.mq_url)
    js = nc.jetstream()
    await js.publish("server.task",
                     utils.pack_msg(TaskBatch(task_name=task_name, batch=(await file.read()).decode().split("\n"))),
                     stream="task")


@app.on_event("startup")
async def startup_event():
    init_logging()


class UserViewModel(BaseModel):
    id: int
    name: str
    total: int
    in_work: int
    completed: int
    online: bool


async def users_view(session) -> list[dict]:
    stmt, users = await get_users_info(session, True)
    nc: Client = await nats.connect(settings.mq_url)
    kv = await nc.jetstream().key_value("connected_users")

    logger.debug(stmt)
    return [UserViewModel(id=user[0], name=user[1], total=user[2], in_work=user[3],
                          completed=user[4], online=(await kv.get(f"{user[0]}")).value != b"not connected").dict()
            for user in users]


async def tasks_view(session):
    stmt, tasks = await get_tasks_info(session, True)
    logger.info(f"{stmt}")
    return [
        {"id": task[0], "name": task[1], "total": task[2], "completed": task[3]} for task in
        tasks
    ]


class UserUpdate(BaseModel):
    id: int
    online: bool


@app.post("/api/users")
async def add_user(name: str = Form(...), session: AsyncSession = Depends(get_session_)):
    try:
        user = User(username=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        nc: Client = await nats.connect(settings.mq_url)
        await (await nc.jetstream().key_value("connected_users")).create(user.id, b'not connected')
    except Exception as e:
        return JSONResponse({"id": -1})
    return JSONResponse(
        {"name": user.username, "id": user.id, "in_work": 0, "total": 0, "completed": 0, "online": False})


@app.get('/api/users')
async def index(session: AsyncSession = Depends(get_session_)):
    try:
        return JSONResponse(await users_view(session))
    except Exception as e:
        logger.error(e)
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.delete('/api/users')
async def index(user: dict = Body(...), session: AsyncSession = Depends(get_session_)):
    try:
        nc = await nats.connect(settings.mq_url)
        # await nc.jetstream().publish("server.task")
        related_numbers: list[Number] = (
            await session.execute(select(Number).where(Number.user_id == user.get('id')))
        ).scalars().all()
        for number in related_numbers:
            await session.delete(number)
        await session.commit()
        for key, nums in groupby(related_numbers, lambda x: x.task_id):
            task: Task | None = (await session.execute(select(Task).where(Task.id == key))).scalar_one_or_none()
            if task is None:
                continue
            await nc.jetstream().publish(
                subject="server.task", stream="task",
                payload=utils.pack_msg(TaskBatch(
                    task_name=task.name, batch=tuple([num.number for num in nums])
                ))
            )

        await session.delete(await session.get(User, user.get('id')))
        await session.commit()
        return JSONResponse({"id": user.get('id')})
    except Exception as e:
        logger.error(e)
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.post('/api/tasks')
async def upload(background_tasks: BackgroundTasks, task_name: str = Form(...),
                 file: UploadFile = Form(...)):
    try:
        background_tasks.add_task(
            create_task, task_name, file
        )
        return JSONResponse({"file": {
            "filename": file.filename, "count": file.size, "task": task_name
        }})
    except Exception as e:
        logger.error(e)


@app.get('/api/tasks')
async def tasks(session: AsyncSession = Depends(get_session_)):
    try:
        return JSONResponse(await tasks_view(session))
    except Exception as e:
        logger.error(e)
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.get('/api/tasks/:id')
async def get_archive(task_id: int, session: AsyncSession = Depends(get_session_)):
    """

    """
    pass


@app.get('/api/ws')
async def ws(websocket: WebSocket):
    pass
