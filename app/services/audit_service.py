"""
Audit logging service.

Writes one row to audit.api_error_log for every exception that surfaces
through the FastAPI exception handlers.  Uses its own short-lived DB session
so a rolled-back request session never prevents the audit write.
"""

from __future__ import annotations

import json
import traceback
import uuid
from typing import Optional

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.audit import ApiErrorLog

_MAX_BODY_BYTES = 10_240  # 10 KB — skip capturing larger payloads


async def log_api_error(
    request: Request,
    status_code: int,
    error_category: str,
    error_message: str,
    error_code: Optional[str] = None,
    validation_errors: Optional[dict] = None,
    exc: Optional[BaseException] = None,
) -> None:
    """Persist one audit row.  Never raises — logging must not affect the response."""
    try:
        # ---- request body (best-effort, size-capped) ----------------------
        request_body: Optional[dict] = None
        try:
            raw = await request.body()
            if raw and len(raw) <= _MAX_BODY_BYTES:
                request_body = json.loads(raw)
        except Exception:
            pass

        # ---- optional request-id header -----------------------------------
        request_id: Optional[uuid.UUID] = None
        raw_rid = request.headers.get("x-request-id")
        if raw_rid:
            try:
                request_id = uuid.UUID(raw_rid)
            except ValueError:
                pass

        # ---- stack trace ---------------------------------------------------
        stack: Optional[str] = None
        if exc is not None:
            stack = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )

        # ---- write to DB ---------------------------------------------------
        db = SessionLocal()
        try:
            db.add(
                ApiErrorLog(
                    request_id=request_id,
                    http_method=request.method,
                    request_path=request.url.path,
                    query_string=str(request.url.query) or None,
                    status_code=status_code,
                    error_category=error_category,
                    error_code=error_code,
                    error_message=error_message,
                    validation_errors=validation_errors,
                    request_body=request_body,
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    device_id=request.headers.get("x-device-id"),
                    stack_trace=stack,
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        finally:
            db.close()

    except Exception:
        # Audit logging must never interfere with returning the error response.
        pass
