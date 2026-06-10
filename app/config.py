"""
Configuration and secrets management for FS Bus API.

Secrets are loaded from environment variables first; if absent they are
fetched from Google Cloud Secret Manager (works both locally via
Application Default Credentials and inside Cloud Run).
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings

from app.firebase_identity import DEFAULT_FIREBASE_WEB_API_KEY

# ---------------------------------------------------------------------------
# Secret Manager helper
# ---------------------------------------------------------------------------


def _fetch_secret(project_id: str, secret_id: str) -> str | None:
    """Fetch the latest version of *secret_id* from GCloud Secret Manager.

    Returns ``None`` when the secret cannot be retrieved so that callers can
    decide how to handle a missing value (e.g. use a default for local dev or
    raise an error in production).
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    try:
        from google.cloud import secretmanager  # noqa: PLC0415
        from google.api_core import exceptions as gcp_exceptions  # noqa: PLC0415

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()
    except (
        Exception  # noqa: BLE001 — narrowed below via isinstance checks in callers
    ) as exc:
        # Only log the error type/message, never the secret value itself.
        logger.warning(
            "Could not fetch secret '%s' from Secret Manager: %s: %s",
            secret_id,
            type(exc).__name__,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables (or an optional `.env` file).
    Any value that is empty **and** has a matching ``SECRET_NAME_<FIELD>``
    mapping is then fetched from GCloud Secret Manager at startup.
    """

    app_name: str = "FS Bus API"
    google_cloud_project: str = "bus-track-480813"

    # Database (CloudSQL / PostgreSQL)
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""

    # OAuth2 / JWT
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Firebase Authentication
    firebase_project_id: str = "bus-track-480813"
    firebase_web_api_key: str = DEFAULT_FIREBASE_WEB_API_KEY
    firebase_check_revoked: bool = False
    firebase_clock_skew_seconds: int = 30
    enable_test_auth_endpoints: bool = True
    docs_required_role: str = "Admin"

    # Google Cloud Storage
    gcs_bucket_name: str = ""
    load_gcp_secrets: bool = True

    # Error alert email
    alert_email_enabled: bool = True
    alert_email_to: list[str] = [
        "shedo.seabela@macrocomm.co.za",
        "erlo.conradie@macrocomm.co.za",
    ]
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_use_ssl: bool = False
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "FS Bus API"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # API CORS — comma-separated list of allowed origins.
    # Set to "*" to allow all origins (development only).
    cors_origins: str = (
        "http://localhost:3000,http://localhost:8000,"
        "https://bus-track-api-379989015900.africa-south1.run.app"
    )

    # Map of field name -> Secret Manager secret ID
    _SECRET_MAP: dict[str, str] = {
        "secret_key": "api-secret-key",
        "db_password": "db-password",
        "db_name": "db-name",
        "db_user": "db-user",
        "gcs_bucket_name": "gcs_bucket",
        "smtp_password": "SMTP_PASSWORD",
        "smtp_username": "SMTP_USERNAME",
        "smtp_from_email": "SMTP_FROM_EMAIL",
        "smtp_from_name": "SMTP_FROM_NAME",
        "smtp_host": "SMTP_HOST",
        "smtp_port": "SMTP_PORT",
        "smtp_use_ssl": "SMTP_USE_SSL",
    }

    def load_from_secret_manager(self) -> None:
        """Populate any still-empty settings from Google Secret Manager.

        The normal precedence is:
        1. environment variables or values from ``.env``
        2. Secret Manager fallback for selected sensitive fields

        This lets local development override values directly while production
        can keep secrets out of the filesystem and deployment manifests.
        """
        import logging  # noqa: PLC0415

        logger = logging.getLogger(__name__)
        if not self.load_gcp_secrets:
            logger.info("Skipping Secret Manager lookup because load_gcp_secrets=false")
            return
        for field, secret_id in self._SECRET_MAP.items():
            if not getattr(self, field):
                value = _fetch_secret(self.google_cloud_project, secret_id)
                if value is None:
                    logger.warning(
                        "Secret '%s' could not be loaded from Secret Manager.",
                        secret_id,
                    )
                else:
                    field_type = (
                        self.model_fields[field].annotation
                        if hasattr(self, "model_fields")
                        else None
                    )
                    try:
                        if field_type is int or field == "smtp_port":
                            typed_value = int(value)
                        elif field_type is bool or field == "smtp_use_ssl":
                            typed_value = value.strip().lower() in ("true", "1", "yes")
                        else:
                            typed_value = value
                    except (ValueError, AttributeError):
                        typed_value = value
                    object.__setattr__(self, field, typed_value)


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance for the lifetime of the process.

    Loading configuration can trigger Secret Manager lookups, so we cache the
    result once and reuse it everywhere. This keeps startup predictable and
    avoids repeated network calls during request handling.
    """
    settings = Settings()
    settings.load_from_secret_manager()
    return settings
