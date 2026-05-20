from __future__ import annotations

import httpx
from pydantic import BaseModel

FIREBASE_PASSWORD_SIGN_IN_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_TOKEN_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# Firebase Web API keys are public client configuration, not secrets.
DEFAULT_FIREBASE_WEB_API_KEY = "AIzaSyDh21k62KCpURRdmM_zQXozBtJJQ3HHxhA"


class FirebaseIdentityError(Exception):
    """Base error raised when Firebase identity operations fail."""

    pass


class FirebaseInvalidCredentialsError(FirebaseIdentityError):
    """Raised when Firebase reports that the login or refresh token is invalid."""

    pass


class FirebasePasswordSignInRequest(BaseModel):
    """Request body for email-and-password Firebase sign-in."""

    email: str
    password: str


class FirebasePasswordSignInResult(BaseModel):
    """Normalized result returned after a successful Firebase password sign-in."""

    provider: str = "firebase"
    id_token: str
    refresh_token: str
    expires_in: int
    email: str | None = None
    local_id: str | None = None
    registered: bool | None = None


class FirebaseRefreshRequest(BaseModel):
    """Request body used to exchange a refresh token for a new ID token."""

    refresh_token: str


class FirebaseRefreshResult(BaseModel):
    """Normalized result returned after a successful token refresh."""

    provider: str = "firebase"
    id_token: str
    refresh_token: str
    expires_in: int


def _extract_error_code(response: httpx.Response) -> str:
    """Pull Firebase's machine-readable error code out of an HTTP response.

    Firebase wraps errors inside a nested JSON structure. This helper isolates
    that parsing so the sign-in and refresh functions can share the same logic.
    """
    try:
        data = response.json()
    except ValueError:
        return ""
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return ""
    message = error.get("message")
    return message if isinstance(message, str) else ""


def sign_in_with_email_password(
    api_key: str,
    email: str,
    password: str,
    timeout_seconds: float = 10.0,
) -> FirebasePasswordSignInResult:
    """Call Firebase's password sign-in API and normalize the response.

    This function is intentionally small and predictable: it sends the request,
    translates common Firebase error codes into domain-specific exceptions, and
    returns a typed result object for the rest of the application.
    """
    if not api_key:
        raise FirebaseIdentityError("Firebase Web API key is not configured.")

    response = httpx.post(
        f"{FIREBASE_PASSWORD_SIGN_IN_URL}?key={api_key}",
        json={
            "email": email,
            "password": password,
            "returnSecureToken": True,
        },
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        error_code = _extract_error_code(response)
        if error_code in {
            "INVALID_LOGIN_CREDENTIALS",
            "EMAIL_NOT_FOUND",
            "INVALID_PASSWORD",
            "USER_DISABLED",
        }:
            raise FirebaseInvalidCredentialsError(
                error_code or "Invalid email or password"
            )
        raise FirebaseIdentityError(error_code or "Firebase sign-in failed.")

    payload = response.json()
    return FirebasePasswordSignInResult(
        id_token=payload["idToken"],
        refresh_token=payload["refreshToken"],
        expires_in=int(payload["expiresIn"]),
        email=payload.get("email"),
        local_id=payload.get("localId"),
        registered=payload.get("registered"),
    )


def refresh_id_token(
    api_key: str,
    refresh_token: str,
    timeout_seconds: float = 10.0,
) -> FirebaseRefreshResult:
    """Exchange a Firebase refresh token for a new ID token.

    Clients call this when their short-lived ID token expires. The refresh
    token is longer lived, so Firebase can issue a fresh access token without
    forcing the user to sign in again.
    """
    if not api_key:
        raise FirebaseIdentityError("Firebase Web API key is not configured.")

    response = httpx.post(
        f"{FIREBASE_TOKEN_REFRESH_URL}?key={api_key}",
        json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        error_code = _extract_error_code(response)
        if error_code in {"TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN", "USER_DISABLED"}:
            raise FirebaseInvalidCredentialsError(
                error_code or "Invalid or expired refresh token"
            )
        raise FirebaseIdentityError(error_code or "Firebase token refresh failed.")

    payload = response.json()
    return FirebaseRefreshResult(
        id_token=payload["id_token"],
        refresh_token=payload["refresh_token"],
        expires_in=int(payload["expires_in"]),
    )
