"""Published timetable versions and the departures captured in each version."""

from datetime import datetime, time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScheduleVersion(Base):
    __tablename__ = "schedule_version"
    __table_args__ = (
        CheckConstraint("row_count > 0"),
        Index("uq_schedule_version_active_operator", "operator_id", unique=True,
              postgresql_where=text("is_active"), sqlite_where=text("is_active")),
        {"schema": "routes"},
    )

    uid: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=func.gen_random_uuid())
    operator_id: Mapped[int] = mapped_column(ForeignKey("master_data.operator.operator_id"))
    source_name: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Departure(Base):
    __tablename__ = "departure"
    __table_args__ = (
        UniqueConstraint("schedule_uid", "duty_no", "departure", "origin", "destination", "direction", "valid_days", "bus_type", name="uq_departure_schedule_row"),
        *(CheckConstraint(f"length(trim({column})) > 0") for column in
          ("duty_no", "origin", "destination", "direction", "valid_days", "bus_type")),
        {"schema": "routes"},
    )

    uid: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4, server_default=func.gen_random_uuid())
    schedule_uid: Mapped[UUID] = mapped_column(ForeignKey("routes.schedule_version.uid"))
    duty_no: Mapped[str] = mapped_column(Text)
    departure: Mapped[time] = mapped_column(Time)
    origin: Mapped[str] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text)
    valid_days: Mapped[str] = mapped_column(Text)
    bus_type: Mapped[str] = mapped_column(Text)
