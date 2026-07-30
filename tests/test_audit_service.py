import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from app.services.audit_service import log_api_success


class FakeRequest:
    method = "POST"
    headers = {}
    client = SimpleNamespace(host="127.0.0.1")
    url = SimpleNamespace(path="/shift/create_shift/", query="")

    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    async def body(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.closed = False

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class AuditServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_log_api_success_writes_success_payload_to_audit_table(self):
        db = FakeSession()
        payload = {
            "user_id": "monitor-uid",
            "busses": [
                {
                    "bus_number": "7025",
                    "inspections": {
                        "external": {
                            "other": {
                                "pass_": False,
                                "reason": "",
                            },
                        },
                    },
                },
            ],
        }

        with patch("app.services.audit_service.SessionLocal", return_value=db):
            await log_api_success(
                FakeRequest(payload),
                status_code=201,
                success_category="SUCCESS",
                success_code="SHIFT_CREATED",
                success_message="Shift created successfully: shift_id=123",
            )

        self.assertTrue(db.committed)
        self.assertTrue(db.closed)
        self.assertEqual(len(db.added), 1)

        audit_row = db.added[0]
        self.assertEqual(audit_row.request_path, "/shift/create_shift/")
        self.assertEqual(audit_row.status_code, 201)
        self.assertEqual(audit_row.error_category, "SUCCESS")
        self.assertEqual(audit_row.error_code, "SHIFT_CREATED")
        self.assertEqual(audit_row.request_body, payload)
        self.assertIsNone(audit_row.validation_errors)

    async def test_log_api_success_uses_supplied_payload(self):
        db = FakeSession()
        original_payload = {"ignored": True}
        supplied_payload = {
            "user_id": "monitor-uid",
            "busses": [{"bus_number": "7025"}],
        }

        with patch("app.services.audit_service.SessionLocal", return_value=db):
            await log_api_success(
                FakeRequest(original_payload),
                status_code=201,
                success_category="SUCCESS",
                success_code="SHIFT_CREATED",
                success_message="Shift created successfully: shift_id=124",
                request_body=supplied_payload,
            )

        self.assertTrue(db.committed)
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.added[0].request_body, supplied_payload)

    async def test_log_api_success_accepts_request_context_without_request(self):
        db = FakeSession()
        supplied_payload = {
            "shift_id": 124,
            "repairs": [{"original_value": "", "defaulted_to": "0-5 mins"}],
        }

        with patch("app.services.audit_service.SessionLocal", return_value=db):
            await log_api_success(
                None,
                status_code=201,
                success_category="PAYLOAD_NORMALIZED",
                success_code="BEHIND_SCHEDULE_INTERVAL_DEFAULTED",
                success_message="Invalid interval defaulted",
                request_body=supplied_payload,
                request_context={
                    "request_id": "f1d5f66b-16c2-42f2-a0aa-44955e0987fb",
                    "authorization": "",
                    "http_method": "POST",
                    "request_path": "/shift/create_shift/",
                    "query_string": None,
                    "client_ip": "127.0.0.1",
                    "user_agent": "test-agent",
                    "device_id": "device-1",
                },
            )

        self.assertTrue(db.committed)
        self.assertEqual(len(db.added), 1)
        audit_row = db.added[0]
        self.assertEqual(audit_row.request_path, "/shift/create_shift/")
        self.assertEqual(audit_row.error_category, "PAYLOAD_NORMALIZED")
        self.assertEqual(audit_row.error_code, "BEHIND_SCHEDULE_INTERVAL_DEFAULTED")
        self.assertEqual(audit_row.request_body, supplied_payload)
        self.assertEqual(audit_row.user_agent, "test-agent")


if __name__ == "__main__":
    unittest.main()
