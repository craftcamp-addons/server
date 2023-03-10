import enum

from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship

from backend.database.base import Base


class NumberStatus(enum.Enum):
    CREATED = 0
    IN_WORK = 1
    COMPLETED = 2


class Number(Base):
    __tablename__ = 'numbers'

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(unique=True)
    status: Mapped[NumberStatus] = mapped_column(default=NumberStatus.CREATED)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    user: Mapped["User"] = relationship(back_populates="numbers")
    task_id: Mapped[int] = mapped_column(ForeignKey('tasks.id'))
    task: Mapped["Task"] = relationship(back_populates="numbers", lazy="noload")
