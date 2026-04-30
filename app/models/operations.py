from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Inspection(Base):
    __tablename__ = "inspection"
    __table_args__ = {"schema": "operations"}

    inspection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    route_text: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inspection_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="submitted", server_default="'submitted'"
    )
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InspectionCheck(Base):
    __tablename__ = "inspection_check"
    __table_args__ = {"schema": "operations"}

    inspection_check_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section: Mapped[str] = mapped_column(String, nullable=False)
    check_code: Mapped[str] = mapped_column(String, nullable=False)
    check_label: Mapped[str] = mapped_column(String, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class InspectionPhoto(Base):
    __tablename__ = "inspection_photo"
    __table_args__ = {"schema": "operations"}

    photo_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inspection_check_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class PassengerCount(Base):
    __tablename__ = "passenger_count"
    __table_args__ = {"schema": "operations"}

    count_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    route_text: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    passenger_count: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
