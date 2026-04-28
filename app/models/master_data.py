from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Route(Base):
    __tablename__ = "route"
    __table_args__ = (
        UniqueConstraint("route_code", "operator_name", name="uq_route_code_operator"),
        {"schema": "master_data"},
    )

    route_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_code: Mapped[str] = mapped_column(String, nullable=False)
    route_name: Mapped[str | None] = mapped_column(String, nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class RouteStop(Base):
    __tablename__ = "route_stop"
    __table_args__ = ({"schema": "master_data"},)

    stop_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("master_data.route.route_id", ondelete="CASCADE"),
        nullable=False,
    )
    route_code: Mapped[str] = mapped_column(String(50), nullable=False)
    stop_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    gps_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    km_from_start: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )


class Vehicle(Base):
    __tablename__ = "vehicle"
    __table_args__ = {"schema": "master_data"}

    vehicle_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vin: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    registration_number: Mapped[str | None] = mapped_column(String, nullable=True)
    fleet_number: Mapped[str | None] = mapped_column(String, nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String, nullable=True)
    make: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[str | None] = mapped_column(String, nullable=True)
    engine_number: Mapped[str | None] = mapped_column(String, nullable=True)
    gvm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tare: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chassis_no: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_1st_registration: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
