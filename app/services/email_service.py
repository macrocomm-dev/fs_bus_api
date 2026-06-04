"""Error alert email service.

Sends a plain-text notification email whenever an unhandled exception occurs
in any API router.  All SMTP settings come from ``app.config.Settings`` so
they can be supplied via environment variables or Google Secret Manager.

Usage::

    from app.services.email_service import send_error_alert

    except Exception as exc:
        send_error_alert(exc, context="POST /shift/create_shift/")
        raise HTTPException(...)
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import traceback
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


def extract_user_id_from_request(request: "Request") -> str | None:
    """Decode the bearer token unverified claims to get the Firebase UID.

    Never raises — returns None on any failure.
    """
    try:
        from jose import jwt as jose_jwt  # noqa: PLC0415

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        claims = jose_jwt.get_unverified_claims(token)
        # uid = claims.get("sub") or claims.get("uid")
        email = claims.get("email")
        name = claims.get("name")
        parts = [p for p in [name, email] if p]
        return " | ".join(parts) if parts else None
    except Exception:  # noqa: BLE001
        return None


async def send_error_alert(
    exc: Exception,
    context: str = "",
    user_id: str | None = None,
) -> None:
    """Send an error-alert email in a fire-and-forget fashion.

    Failures inside this function are logged but never re-raised so that the
    original exception handling path is not disrupted.

    Args:
        exc:      The exception that was caught.
        context:  Human-readable label for where the error occurred,
                  e.g. ``"POST /shift/create_shift/"``.
        user_id:  Optional Firebase UID of the authenticated caller.
    """
    # Import here to avoid a circular-import at module load time.
    from app.config import get_settings  # noqa: PLC0415

    settings = get_settings()

    if not settings.alert_email_enabled:
        return

    missing = [
        field
        for field in (
            "smtp_from_email",
            "smtp_username",
            "smtp_password",
        )
        if not getattr(settings, field)
    ]
    if missing or not settings.alert_email_to:
        logger.warning(
            "Error alert email skipped — missing settings: %s", ", ".join(missing)
        )
        return

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tb = traceback.format_exc()

        body_lines = [
            f"Time      : {timestamp}",
            f"Context   : {context or 'unknown'}",
            f"User      : {user_id or 'unknown'}",
            f"Exception : {type(exc).__name__}: {exc}",
            "",
            "Traceback:",
            tb,
        ]
        body = "\n".join(body_lines)

        msg = MIMEText(body, "plain")
        msg["Subject"] = f"[FS Bus API] Unhandled error in {context or 'unknown'}"
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        msg["To"] = ", ".join(settings.alert_email_to)

        if settings.smtp_use_ssl:
            smtp_cls = smtplib.SMTP_SSL

            def _connect(smtp: smtplib.SMTP) -> None:  # type: ignore[misc]
                smtp.ehlo()

        else:
            smtp_cls = smtplib.SMTP  # type: ignore[assignment]

            def _connect(smtp: smtplib.SMTP) -> None:  # type: ignore[misc]
                smtp.ehlo()
                smtp.starttls()

        def _send() -> None:
            with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                _connect(smtp)
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(
                    settings.smtp_from_email,
                    settings.alert_email_to,
                    msg.as_string(),
                )

        await asyncio.to_thread(_send)

        logger.info("Error alert email sent for context '%s'.", context)

    except Exception as mail_exc:  # noqa: BLE001
        logger.error(
            "Failed to send error alert email for context '%s': %s",
            context,
            mail_exc,
        )
