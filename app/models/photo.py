from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.bus_inspection import BusInspection
    from app.models.shift import Shift


class Photo(Base):
    """Database row for one inspection photo in the new shift-based workflow."""

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
    inspection_item: Mapped[str] = mapped_column(String, nullable=False)
    photo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    inspection: Mapped[BusInspection] = relationship(
        "BusInspection", back_populates="photos"
    )


class DestinationDisplayPhoto(Base):
    """Bus-level evidence, independent of optional inspection events and counts."""

    __tablename__ = "destination_display"
    __table_args__ = (Index("ix_destination_display_bus_group", "shift_id", "bus_id", "duty_number", "replacement_bus"), {"schema": "photos"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("shifts.shifts.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    bus_id: Mapped[str] = mapped_column(String, nullable=False)
    fleet_number: Mapped[str] = mapped_column(String, nullable=False)
    duty_number: Mapped[str] = mapped_column(String, nullable=False)
    replacement_bus: Mapped[bool] = mapped_column(Boolean, nullable=False)
    license_disk_scan_succeeded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    destination_displayed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    photo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class Selfie(Base):
    """Database row for one selfie captured during a shift."""

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
    photo: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )

    # Relationships
    shift: Mapped[Shift] = relationship("Shift", back_populates="selfies")
