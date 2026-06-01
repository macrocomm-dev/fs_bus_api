from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.app_auth import AppUser
    from app.models.photo import Photo


class BusInspection(Base):
    """Flat inspection storage row used by the shift workflow.

    Even though the API speaks in grouped sections like external/internal/
    driver, the database stores each inspection event as its own row in this
    table.
    """

    __tablename__ = "inspections"
    __table_args__ = {"schema": "inspections"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("shifts.shifts.id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("app_auth.app_user.firebase_uid"), nullable=False
    )
    bus_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    fleet_number: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    duty_number: Mapped[str | None] = mapped_column(String, nullable=True)
    replacement_bus: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    internal_inspection_id: Mapped[str] = mapped_column(String, nullable=False)
    inspection_type: Mapped[str] = mapped_column(String, nullable=False)
    inspection_time: Mapped[datetime] = mapped_column(nullable=False)
    inspection_lat: Mapped[float] = mapped_column(Float, nullable=False)
    inspection_lon: Mapped[float] = mapped_column(Float, nullable=False)
    count: Mapped[int] = mapped_column(
        BigInteger, nullable=True, default=0, server_default="0"
    )
    pass_: Mapped[bool] = mapped_column(
        "pass", Boolean, nullable=True, default=True, server_default="true"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tyres_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tyres_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    windows_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    windows_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ext_other_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ext_other_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fire_extinguisher_present: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    seats_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    seats_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    aisle_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    aisle_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    int_other_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    int_other_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    number_seated: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    number_standing: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    behind_schedule_interval: Mapped[str | None] = mapped_column(String, nullable=True)
    # Bus / driver identification (moved from shifts table)
    license_disk_scan_succeeded: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    destination_displayed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    prdp_scan_succeeded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    prdp_expiry_date: Mapped[datetime | None] = mapped_column(nullable=True)
    driver_identified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    driver_fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    shift: Mapped[Shift] = relationship("Shift", back_populates="inspections")
    photos: Mapped[list[Photo]] = relationship("Photo", back_populates="inspection")
    user: Mapped[AppUser] = relationship(
        "AppUser", back_populates="inspections", foreign_keys="[BusInspection.user_id]"
    )
