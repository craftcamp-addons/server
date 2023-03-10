import datetime
from typing import List

from sqlalchemy.orm import mapped_column, Mapped, relationship

from backend.database.base import Base


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=True)
    numbers: Mapped[List["Number"]] = relationship("Number", back_populates="task")

    created_at: Mapped[datetime.datetime] = mapped_column()
