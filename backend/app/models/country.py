from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Country(Base):
    __tablename__ = "country"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True)  # ISO 3166-1 alpha-2
    name_en: Mapped[str] = mapped_column(String(100))
    name_zh: Mapped[str] = mapped_column(String(100))
    flag_emoji: Mapped[str] = mapped_column(String(8))
    tier: Mapped[int] = mapped_column(Integer, default=1)  # 1 / 2 / 3 (low-frequency)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
