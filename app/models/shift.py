from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.app_auth import AppUser
    from app.models.bus_inspection import BusInspection
    from app.models.photo import Selfie


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = {"schema": "shifts"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_auth.app_user.user_id"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_lon: Mapped[float] = mapped_column(Float, nullable=False)
    end_lat: Mapped[float] = mapped_column(Float, nullable=False)
    end_lon: Mapped[float] = mapped_column(Float, nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped[AppUser] = relationship("AppUser", back_populates="shifts")
    inspections: Mapped[list[BusInspection]] = relationship(
        "BusInspection", back_populates="shift"
    )
    selfies: Mapped[list[Selfie]] = relationship("Selfie", back_populates="shift")
