from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.bus_inspection import BusInspection


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"schema": "app_auth"}

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    firebase_uid: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("master_data.operator.operator_id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    shifts: Mapped[list[Shift]] = relationship("Shift", back_populates="user")
    inspections: Mapped[list[BusInspection]] = relationship(
        "BusInspection", back_populates="user", foreign_keys="[BusInspection.user_id]"
    )
