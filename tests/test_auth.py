import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import TokenData, expand_role_permissions, require_role
from app.config import Settings, get_settings
from app.database import get_db
from app.firebase_identity import (
    FirebaseInvalidCredentialsError,
    FirebasePasswordSignInResult,
    FirebaseRefreshResult,
)
from app.main import app


client = TestClient(app)


class AuthTests(unittest.TestCase):

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_expand_role_permissions_respects_hierarchy(self):
        self.assertEqual(
            expand_role_permissions("Admin"),
            ("Monitor", "Supervisor", "Admin"),
        )
        self.assertEqual(
            expand_role_permissions("Supervisor"),
            ("Monitor", "Supervisor"),
        )

    def test_require_role_accepts_inherited_permissions(self):
        dependency = require_role("Monitor")
        current_user = TokenData(sub="user-123", role="Admin")

        returned_user = dependency(current_user)

        self.assertEqual(returned_user, current_user)

    def test_require_role_rejects_insufficient_permissions(self):
        dependency = require_role("Admin")
        current_user = TokenData(sub="user-123", role="Monitor")

        with self.assertRaises(HTTPException) as raised:
            dependency(current_user)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Insufficient permissions")

    def test_me_returns_firebase_identity_claims(self):
        payload = {
            "uid": "user-123",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "role": "Supervisor",
        }

        with patch("app.auth.firebase_auth.verify_id_token", return_value=payload), patch(
            "app.auth.get_firebase_app", return_value=object()
        ):
            response = client.get(
                "/me",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "sub": "user-123",
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "role": "Supervisor",
                "permissions": ["Monitor", "Supervisor"],
            },
        )

    def test_auth_test_whoami_returns_provider_and_user(self):
        payload = {
            "uid": "user-456",
            "name": "Grace Hopper",
            "email": "grace@example.com",
            "role": "Admin",
        }

        with patch(
            "app.auth.firebase_auth.verify_id_token", return_value=payload
        ), patch("app.auth.get_firebase_app", return_value=object()):
            response = client.get(
                "/auth/test/whoami",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "provider": "firebase",
                "user": {
                    "sub": "user-456",
                    "name": "Grace Hopper",
                    "email": "grace@example.com",
                    "role": "Admin",
                    "permissions": ["Monitor", "Supervisor", "Admin"],
                },
            },
        )

    def test_openapi_requires_authentication(self):
        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Could not validate credentials")

    def test_docs_shell_contains_test_sign_in_form(self):
        response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Test Sign-In", response.text)
        self.assertIn("/auth/test/token", response.text)
        self.assertIn("Load Protected Docs", response.text)

    def test_openapi_respects_docs_role(self):
        payload = {
            "uid": "user-123",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "role": "Supervisor",
        }

        with patch(
            "app.auth.firebase_auth.verify_id_token", return_value=payload
        ), patch("app.auth.get_firebase_app", return_value=object()):
            response = client.get(
                "/openapi.json",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Insufficient permissions")

    def test_openapi_returns_schema_for_admin(self):
        payload = {
            "uid": "user-789",
            "name": "Linus Torvalds",
            "email": "linus@example.com",
            "role": "Admin",
        }

        with patch(
            "app.auth.firebase_auth.verify_id_token", return_value=payload
        ), patch("app.auth.get_firebase_app", return_value=object()):
            response = client.get(
                "/openapi.json",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["info"]["title"], "FS Bus API")
        self.assertEqual(response.json()["openapi"], "3.0.3")

    def test_auth_test_token_returns_firebase_token_payload(self):
        result = FirebasePasswordSignInResult(
            id_token="firebase-id-token",
            refresh_token="firebase-refresh-token",
            expires_in=3600,
            email="admin.test@fsbus.example.com",
            local_id="firebase-local-id",
            registered=True,
        )

        with patch("app.main.sign_in_with_email_password", return_value=result):
            response = client.post(
                "/auth/test/token",
                json={
                    "email": "admin.test@fsbus.example.com",
                    "password": "example-password",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id_token"], "firebase-id-token")
        self.assertEqual(response.json()["provider"], "firebase")

    def test_authentication_get_token_returns_name_surname_and_role(self):
        result = FirebasePasswordSignInResult(
            id_token="firebase-id-token",
            refresh_token="firebase-refresh-token",
            expires_in=3600,
            email="ada@example.com",
            local_id="firebase-local-id",
            registered=True,
        )

        app_user = SimpleNamespace(
            firebase_uid="firebase-local-id",
            role="Supervisor",
            name="Ada",
            surname="Lovelace",
            full_name="Ada Lovelace",
        )

        class FakeQuery:
            def __init__(self, user):
                self.user = user

            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return self.user

        class FakeDb:
            def query(self, model):
                return FakeQuery(app_user)

        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db

        with patch(
            "app.routers.authentication.sign_in_with_email_password",
            return_value=result,
        ):
            response = client.post(
                "/authentication/get_token",
                json={
                    "email": "ada@example.com",
                    "password": "example-password",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "firebase-id-token")
        self.assertEqual(response.json()["role"], "Supervisor")
        self.assertEqual(response.json()["user_id"], "firebase-local-id")
        self.assertEqual(response.json()["name"], "Ada")
        self.assertEqual(response.json()["surname"], "Lovelace")
        self.assertIsNotNone(response.json()["expires_at"])
        self.assertIsNotNone(response.json()["expires_at"])

    def test_auth_refresh_returns_name_surname_and_role(self):
        result = FirebaseRefreshResult(
            id_token="refreshed-id-token",
            refresh_token="new-refresh-token",
            expires_in=3600,
        )

        app_user = SimpleNamespace(
            firebase_uid="firebase-local-id",
            role="Supervisor",
            name="Ada",
            surname="Lovelace",
            full_name="Ada Lovelace",
        )

        class FakeQuery:
            def __init__(self, user):
                self.user = user

            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return self.user

        class FakeDb:
            def query(self, model):
                return FakeQuery(app_user)

        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db

        refreshed_token_data = TokenData(
            sub="firebase-local-id",
            name="Ada Lovelace",
            email="ada@example.com",
            role="Supervisor",
        )

        with patch("app.main.refresh_id_token", return_value=result), patch(
            "app.main.decode_access_token",
            return_value=refreshed_token_data,
        ):
            response = client.post(
                "/auth/refresh",
                json={
                    "refresh_token": "old-refresh-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "refreshed-id-token")
        self.assertEqual(response.json()["refresh_token"], "new-refresh-token")
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertEqual(response.json()["role"], "Supervisor")
        self.assertEqual(response.json()["user_id"], "firebase-local-id")
        self.assertEqual(response.json()["name"], "Ada")
        self.assertEqual(response.json()["surname"], "Lovelace")

    def test_auth_refresh_rejects_unknown_user(self):
        result = FirebaseRefreshResult(
            id_token="refreshed-id-token",
            refresh_token="new-refresh-token",
            expires_in=3600,
        )

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return None

        class FakeDb:
            def query(self, model):
                return FakeQuery()

        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db

        refreshed_token_data = TokenData(
            sub="missing-user",
            name="Missing User",
            email="missing@example.com",
            role="Supervisor",
        )

        with patch("app.main.refresh_id_token", return_value=result), patch(
            "app.main.decode_access_token",
            return_value=refreshed_token_data,
        ):
            response = client.post(
                "/auth/refresh",
                json={
                    "refresh_token": "old-refresh-token",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            "User account not found. Contact an administrator.",
        )

    def test_auth_test_token_rejects_invalid_credentials(self):
        with patch(
            "app.main.sign_in_with_email_password",
            side_effect=FirebaseInvalidCredentialsError("INVALID_LOGIN_CREDENTIALS"),
        ):
            response = client.post(
                "/auth/test/token",
                json={
                    "email": "admin.test@fsbus.example.com",
                    "password": "wrong-password",
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid email or password.")

    def test_auth_test_token_can_be_disabled(self):
        settings = Settings(enable_test_auth_endpoints=False)
        app.dependency_overrides[get_settings] = lambda: settings

        response = client.post(
            "/auth/test/token",
            json={
                "email": "admin.test@fsbus.example.com",
                "password": "example-password",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Test auth endpoints are disabled.")

    def test_docs_shell_hides_test_sign_in_when_disabled(self):
        settings = Settings(enable_test_auth_endpoints=False)
        app.dependency_overrides[get_settings] = lambda: settings

        response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Test auth endpoint is disabled for this environment.", response.text)
        self.assertIn('class="gate hidden"', response.text)

    def test_me_requires_bearer_token(self):
        response = client.get("/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Could not validate credentials")


if __name__ == "__main__":
    unittest.main()
