import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from fastapi.testclient import TestClient

from app.auth import TokenData, get_current_user
from app.config import Settings, get_settings
from app.main import app


client = TestClient(app)


class SmartFleetTests(unittest.TestCase):

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_iframe_login_url_returns_ott_login_link(self):
        app.dependency_overrides[get_current_user] = lambda: TokenData(
            sub="firebase-user-1", role="Admin"
        )
        app.dependency_overrides[get_settings] = lambda: Settings(
            load_gcp_secrets=False,
            smart_fleet_base_url="https://smart-fleet.co.za",
            smart_fleet_email="FreeStateBus@macrocomm.co.za",
            smart_fleet_api_hash="Macrocomm12#",
        )

        fake_response = Mock(status_code=200)
        fake_response.json.return_value = {"token": "ott-token-123"}

        with patch("app.routers.smartfleet.re.post", return_value=fake_response) as post_mock:
            response = client.get(
                "/smartfleet/iframe-login-url",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"iframe_url": "https://smart-fleet.co.za/login?ott=ott-token-123"},
        )
        post_mock.assert_called_once()

    def test_iframe_login_url_returns_gateway_error_when_ott_fails(self):
        app.dependency_overrides[get_current_user] = lambda: TokenData(
            sub="firebase-user-2", role="Admin"
        )
        app.dependency_overrides[get_settings] = lambda: Settings(
            load_gcp_secrets=False,
            smart_fleet_base_url="https://smart-fleet.co.za",
            smart_fleet_email="FreeStateBus@macrocomm.co.za",
            smart_fleet_api_hash="Macrocomm12#",
        )

        fake_response = Mock(status_code=401)
        fake_response.json.return_value = {"status": 0, "message": "Wrong credentials."}

        with patch("app.routers.smartfleet.re.post", return_value=fake_response):
            response = client.get(
                "/smartfleet/iframe-login-url",
                headers={"Authorization": "Bearer firebase-token"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Wrong credentials.")

    def test_iframe_login_url_returns_server_error_when_not_configured(self):
        app.dependency_overrides[get_current_user] = lambda: TokenData(
            sub="firebase-user-3", role="Admin"
        )
        app.dependency_overrides[get_settings] = lambda: Settings(
            load_gcp_secrets=False,
            smart_fleet_base_url="https://smart-fleet.co.za",
            smart_fleet_email="",
            smart_fleet_api_hash="",
        )

        response = client.get(
            "/smartfleet/iframe-login-url",
            headers={"Authorization": "Bearer firebase-token"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Smart Fleet is not configured.")
