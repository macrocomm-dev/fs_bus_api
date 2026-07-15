import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from app.config import Settings
from app.routers.vehicle import _vehicle_smart_fleet_lookup_keys
from app.services.smartfleet_service import get_latest_vehicle_positions


class SmartFleetVehicleMatchingTests(unittest.TestCase):
    def test_grouped_smartfleet_devices_are_keyed_by_registration_tokens(self):
        settings = Settings(
            load_gcp_secrets=False,
            smart_fleet_base_url="https://smart-fleet.co.za",
            smart_fleet_api_hash="hash",
        )

        fake_response = Mock(status_code=200)
        fake_response.json.return_value = [
            {
                "title": "Bophelong Transport",
                "items": [
                    {
                        "id": 2473,
                        "name": "FVT094FS - 3002 B",
                        "address": "Duma Nokwe Road, Bloemfontein",
                        "lat": -29.214208,
                        "lng": 26.841907,
                        "time": "2026-07-15 09:33:54",
                        "device_data": {
                            "name": "FVT094FS - 3002 B",
                            "vin": "AAMHB10476PX30410",
                            "registration_number": "FVT094FS - 3002 B",
                            "plate_number": "FVT094FS - 3002 B",
                        },
                    }
                ],
            }
        ]

        with patch("app.services.smartfleet_service.requests.get", return_value=fake_response):
            positions = get_latest_vehicle_positions(settings)

        self.assertIn("fvt094fs", positions)
        self.assertIn("3002", positions)
        self.assertIn("aamhb10476px30410", positions)
        self.assertEqual(positions["fvt094fs"].smart_fleet_device_id, 2473)
        self.assertEqual(positions["fvt094fs"].last_address, "Duma Nokwe Road, Bloemfontein")
        self.assertEqual(
            positions["fvt094fs"].last_response_time.strftime("%Y-%m-%d %H:%M:%S"),
            "2026-07-15 09:33:54",
        )

    def test_vehicle_smartfleet_lookup_keys_include_local_vin_registration_and_fleet(self):
        vehicle = SimpleNamespace(
            vin="FVT094FS",
            registration_number="FVT 094 FS",
            fleet_number="3002 B",
        )

        keys = _vehicle_smart_fleet_lookup_keys(vehicle)

        self.assertIn("fvt094fs", keys)
        self.assertIn("3002b", keys)
        self.assertIn("3002", keys)
