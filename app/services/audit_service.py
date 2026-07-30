"""Audit logging service.

Writes audit rows to ``audit.api_error_log``. Historically this table only held
errors surfaced through the FastAPI exception handlers. It is now also used for
successful shift payload capture so success and failure request bodies can be
compared in one place.
"""

from __future__ import annotations

import json
import traceback
import uuid
from typing import Optional

from fastapi import Request
from jose import jwt as jose_jwt
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.models.app_auth import AppUser
from app.models.audit import ApiErrorLog

_MAX_BODY_BYTES = 10_240  # 10 KB — skip capturing larger payloads


def build_request_audit_context(request: Request) -> dict:
    """Snapshot request metadata before a background audit task runs."""
    raw_rid = request.headers.get("x-request-id")
    try:
        request_id = str(uuid.UUID(raw_rid)) if raw_rid else str(uuid.uuid4())
    except ValueError:
        request_id = str(uuid.uuid4())

    return {
        "request_id": request_id,
        "authorization": request.headers.get("authorization", ""),
        "http_method": request.method,
        "request_path": request.url.path,
        "query_string": str(request.url.query) or None,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "device_id": request.headers.get("x-device-id"),
    }


async def _read_json_request_body(
    request: Request,
    *,
    max_body_bytes: int | None = _MAX_BODY_BYTES,
) -> Optional[dict]:
    """Return the request JSON body, optionally skipping bodies above a size cap."""
    try:
        raw = await request.body()
        if not raw:
            return None
        if max_body_bytes is not None and len(raw) > max_body_bytes:
            return None
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {"payload": payload}
    except Exception:
        return None


def _resolve_user_id_from_auth_header(auth_header: str, db) -> Optional[int]:
    """Map a bearer token to the local numeric ``user_id``.

    Audit logging should be cheap and resilient, so this helper reads JWT claims
    without doing a network verification call. It is good enough for linking an
    error record back to the local user row when the token contains a Firebase
    UID.
    """
    try:
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        claims = jose_jwt.get_unverified_claims(token)
        firebase_uid = claims.get("sub") or claims.get("uid")
        if not firebase_uid:
            return None
        user = db.query(AppUser).filter(AppUser.firebase_uid == firebase_uid).first()
        return user.user_id if user else None
    except Exception:
        return None


def _resolve_user_id(request: Request, db) -> Optional[int]:
    """Map the bearer token in a request to the local numeric ``user_id``."""
    return _resolve_user_id_from_auth_header(
        request.headers.get("authorization", ""), db
    )


async def log_api_error(
    request: Request,
    status_code: int,
    error_category: str,
    error_message: str,
    error_code: Optional[str] = None,
    validation_errors: Optional[dict] = None,
    exc: Optional[BaseException] = None,
) -> None:
    """Persist one API error audit row without ever breaking the response path.

    This function is deliberately defensive. Even if request-body parsing,
    token inspection, or the audit insert itself fails, the caller should still
    be able to return the original API error response to the client.
    """
    try:
        # ---- request body (best-effort, size-capped) ----------------------
        request_body = await _read_json_request_body(request)

        # ---- optional request-id header (generate one if absent) ----------
        raw_rid = request.headers.get("x-request-id")
        try:
            request_id: uuid.UUID = uuid.UUID(raw_rid) if raw_rid else uuid.uuid4()
        except ValueError:
            request_id = uuid.uuid4()

        # ---- stack trace ---------------------------------------------------
        stack: Optional[str] = None
        if exc is not None:
            stack = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )

        # ---- write to DB ---------------------------------------------------
        db = SessionLocal()
        try:
            numeric_user_id = _resolve_user_id(request, db)
            db.add(
                ApiErrorLog(
                    request_id=request_id,
                    user_id=numeric_user_id,
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


async def log_api_success(
    request: Request | None = None,
    *,
    status_code: int,
    success_category: str,
    success_message: str,
    success_code: Optional[str] = None,
    request_body: Optional[dict] = None,
    request_context: Optional[dict] = None,
) -> None:
    """Persist one successful API request payload without affecting the response."""
    try:
        if request_context is None:
            if request is None:
                return
            request_context = build_request_audit_context(request)

        if request_body is None:
            if request is None:
                return
            request_body = await _read_json_request_body(request, max_body_bytes=None)

        try:
            request_id = uuid.UUID(request_context["request_id"])
        except ValueError:
            request_id = uuid.uuid4()

        db = SessionLocal()
        try:
            numeric_user_id = _resolve_user_id_from_auth_header(
                request_context.get("authorization", ""), db
            )
            db.add(
                ApiErrorLog(
                    request_id=request_id,
                    user_id=numeric_user_id,
                    http_method=request_context.get("http_method", "UNKNOWN"),
                    request_path=request_context.get("request_path", "UNKNOWN"),
                    query_string=request_context.get("query_string"),
                    status_code=status_code,
                    error_category=success_category,
                    error_code=success_code,
                    error_message=success_message,
                    validation_errors=None,
                    request_body=request_body,
                    client_ip=request_context.get("client_ip"),
                    user_agent=request_context.get("user_agent"),
                    device_id=request_context.get("device_id"),
                    stack_trace=None,
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        finally:
            db.close()

    except Exception:
        # Audit logging must never interfere with returning the API response.
        pass
