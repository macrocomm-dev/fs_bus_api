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

from app.config import Settings
from app.services.email_service import send_error_alert


class FakeSmtp:
    sent_messages: list[str] = []

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        return None

    def login(self, username: str, password: str):
        return None

    def sendmail(self, from_addr: str, to_addrs: list[str], message: str):
        self.sent_messages.append(message)


class EmailServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeSmtp.sent_messages.clear()

    async def test_error_alert_includes_runtime_and_request_context(self):
        settings = Settings(
            load_gcp_secrets=False,
            alert_email_enabled=True,
            alert_email_to=["alerts@example.com"],
            smtp_from_email="from@example.com",
            smtp_username="smtp-user",
            smtp_password="smtp-password",
            smtp_from_name="FS Bus API",
            smtp_host="smtp.example.com",
            smtp_port=587,
        )
        request = SimpleNamespace(
            client=SimpleNamespace(host="203.0.113.10"),
            headers={
                "user-agent": "pytest-agent",
                "referer": "https://example.com/live-map",
                "origin": "https://example.com",
                "x-forwarded-for": "198.51.100.22",
                "x-cloud-trace-context": "trace-id/1;o=1",
                "x-device-id": "device-123",
            },
        )

        with patch("app.config.get_settings", return_value=settings), patch(
            "app.services.email_service.smtplib.SMTP", FakeSmtp
        ):
            await send_error_alert(
                RuntimeError("boom"),
                context="GET /example",
                user_id="user@example.com",
                request=request,
            )

        self.assertEqual(len(FakeSmtp.sent_messages), 1)
        message = FakeSmtp.sent_messages[0]
        self.assertIn("Runtime:", message)
        self.assertIn("Hostname", message)
        self.assertIn("Cloud Run revision", message)
        self.assertIn("Request:", message)
        self.assertIn("Client IP           : 203.0.113.10", message)
        self.assertIn("User-Agent          : pytest-agent", message)
        self.assertIn("X-Forwarded-For     : 198.51.100.22", message)
