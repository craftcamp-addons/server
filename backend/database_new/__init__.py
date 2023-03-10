import datetime
import enum

from pony import orm
from pony.orm import db_session, select

from config import settings

db = orm.Database()


class User(db.Entity):
    username = orm.Required(str)
    numbers = orm.Set('Number')


class Task(db.Entity):
    name = orm.Required(str)
    numbers = orm.Set('Number')


class Archive(db.Entity):
    filename = orm.Required(str)
    slug = orm.Required(str)
    created = orm.Required(datetime.datetime)
    task = orm.Required(Task)
    numbers = orm.Set('Number')


class NumberStatus(enum.Enum):
    CREATED = 0
    IN_WORK = 1
    DATA_LOADED = 2
    NO_DATA = 3


class Number(db.Entity):
    number = orm.Required(str)
    status = orm.Required(NumberStatus)
    user = orm.Required(User)
    task = orm.Required(Task)
    archive = orm.Required(Archive)


db.bind(provider='postgres', host=settings.database.host, port=settings.database.port,
        user=settings.database.user, password=settings.database.password, database=settings.database.database,
        create_db=True)

db.generate_mapping(create_tables=True)
