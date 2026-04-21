import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import TokenData, expand_role_permissions, require_role
from app.config import Settings, get_settings
from app.firebase_identity import (
    FirebaseInvalidCredentialsError,
    FirebasePasswordSignInResult,
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

    def test_me_requires_bearer_token(self):
        response = client.get("/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Could not validate credentials")


if __name__ == "__main__":
    unittest.main()
