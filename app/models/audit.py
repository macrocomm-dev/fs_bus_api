from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, BigInteger, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiErrorLog(Base):
    """Audit table row that captures one API error event."""

    __tablename__ = "api_error_log"
    __table_args__ = {"schema": "audit"}

    api_error_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    request_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    http_method: Mapped[str] = mapped_column(String, nullable=False)
    request_path: Mapped[str] = mapped_column(Text, nullable=False)
    query_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_category: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    validation_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    client_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
