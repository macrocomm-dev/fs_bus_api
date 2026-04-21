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
        return response.payload.data.decode("UTF-8")
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
    google_cloud_project: str = "bus_track"

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # API CORS — comma-separated list of allowed origins.
    # Set to "*" to allow all origins (development only).
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # Map of field name -> Secret Manager secret ID
    _SECRET_MAP: dict[str, str] = {
        "secret_key": "api-secret-key",
        "db_password": "db-password",
        "db_name": "db-name",
        "db_user": "db-user",
    }

    def load_from_secret_manager(self) -> None:
        """Populate empty fields from GCloud Secret Manager."""
        import logging  # noqa: PLC0415

        logger = logging.getLogger(__name__)
        for field, secret_id in self._SECRET_MAP.items():
            if not getattr(self, field):
                value = _fetch_secret(self.google_cloud_project, secret_id)
                if value is None:
                    logger.warning(
                        "Secret '%s' could not be loaded from Secret Manager.",
                        secret_id,
                    )
                else:
                    object.__setattr__(self, field, value)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.load_from_secret_manager()
    return settings
