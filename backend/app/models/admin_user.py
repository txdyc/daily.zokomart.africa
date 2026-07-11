from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STAFF_ROLES = ("admin", "auditor", "cs")


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="admin", server_default="admin")
