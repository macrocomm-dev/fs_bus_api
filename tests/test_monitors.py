import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from app.auth import TokenData
from app.routers.monitors import create_shift
from app.schemas.shift import ShiftCreate


class MonitorRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_shift_commits_once_after_nested_records(self):
        shift_data = ShiftCreate.model_validate(
            {
                "user_id": "firebase_uid_abc123",
                "start_time": "2026-05-01T07:00:00",
                "end_time": "2026-05-01T15:30:00",
                "start_lat": -26.2041,
                "start_lon": 28.0473,
                "end_lat": -26.2089,
                "end_lon": 28.0512,
                "device_id": "device_001",
                "selfies": [],
                "busses": [],
            }
        )
        db = SimpleNamespace(
            add=Mock(),
            flush=Mock(),
            commit=Mock(),
            rollback=Mock(),
        )
        current_user = TokenData(sub="user-123", role="Monitor")

        with patch(
            "app.routers.monitors.add_shift_selfies",
            new=AsyncMock(return_value=True),
        ) as add_shift_selfies, patch(
            "app.routers.monitors.add_inspections",
            new=AsyncMock(return_value=True),
        ) as add_inspections:
            response = await create_shift(shift_data=shift_data, db=db, current_user=current_user)

        self.assertEqual(response, {"status": 201, "message": "success"})
        db.flush.assert_called_once()
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        add_shift_selfies.assert_awaited_once()
        add_inspections.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
