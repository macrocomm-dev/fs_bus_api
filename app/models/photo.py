from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Float, ForeignKey, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.bus_inspection import BusInspection
    from app.models.shift import Shift


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = {"schema": "photos"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("inspections.inspections.id"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    photo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    inspection: Mapped[BusInspection] = relationship(
        "BusInspection", back_populates="photos"
    )


class Selfie(Base):
    __tablename__ = "selfies"
    __table_args__ = {"schema": "photos"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shifts.shifts.id"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    photo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    shift: Mapped[Shift] = relationship("Shift", back_populates="selfies")
