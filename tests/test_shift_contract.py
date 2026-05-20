import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from app.routers.inspection import _group_bus_inspection_rows
from app.schemas.shift import ShiftCreate


class ShiftContractTests(unittest.TestCase):

    def test_shift_create_accepts_nested_bus_inspections(self):
        payload = {
            "user_id": "firebase_uid_abc123",
            "start_time": "2026-05-01T07:00:00",
            "end_time": "2026-05-01T15:30:00",
            "start_lat": -26.2041,
            "start_lon": 28.0473,
            "end_lat": -26.2089,
            "end_lon": 28.0512,
            "device_id": "device_001",
            "selfies": [
                {
                    "timestamp": "2026-05-01T07:05:00",
                    "lat": -26.2041,
                    "lon": 28.0473,
                    "photo": "<base64_encoded_image>",
                }
            ],
            "busses": [
                {
                    "bus_id": "VIN0001ZA",
                    "bus_number": "GA 01 001 GP",
                    "license_disk_scan_succeeded": True,
                    "destination_displayed": True,
                    "inspections": {
                        "external_inspected": True,
                        "internal_inspected": True,
                        "driver_inspected": True,
                        "passenger_counts_done": True,
                        "behind_schedule_reports_done": True,
                        "external": {
                            "internal_inspection_id": "ext-1",
                            "inspection_time": "2026-05-01T08:00:00",
                            "inspection_lat": -26.2045,
                            "inspection_lon": 28.0480,
                            "tyres": {"pass_": False, "reason": None, "photos": []},
                            "windows": {"pass_": False, "reason": None, "photos": []},
                            "other": {
                                "pass_": False,
                                "reason": "Body damage",
                                "photos": [
                                    {
                                        "timestamp": "2026-05-01T08:02:00",
                                        "lat": -26.2045,
                                        "lon": 28.0480,
                                        "photo": "damage-photo",
                                    }
                                ],
                            },
                        },
                        "internal": {
                            "internal_inspection_id": "int-1",
                            "inspection_time": "2026-05-01T08:05:00",
                            "inspection_lat": -26.2046,
                            "inspection_lon": 28.0481,
                            "fire_extinguisher_present": True,
                            "seats": {"pass_": False, "reason": None, "photos": []},
                            "aisle": {"pass_": False, "reason": None, "photos": []},
                            "other": {"pass_": False, "reason": None, "photos": []},
                        },
                        "driver": {
                            "internal_inspection_id": "drv-1",
                            "inspection_time": "2026-05-01T08:07:00",
                            "inspection_lat": -26.2047,
                            "inspection_lon": 28.0482,
                            "prdp_scan_succeeded": True,
                            "prdp_expiry_date": "2027-03-15T00:00:00",
                            "driver_identified": True,
                            "driver_fail_reason": None,
                            "driver_name": "Sipho Nkosi",
                        },
                        "passenger_counts": [
                            {
                                "internal_inspection_id": "cnt-1",
                                "inspection_time": "2026-05-01T08:15:00",
                                "inspection_lat": -26.2050,
                                "inspection_lon": 28.0488,
                                "number_seated": 32,
                                "number_standing": 8,
                            }
                        ],
                        "behind_schedule_reports": [
                            {
                                "internal_inspection_id": "sch-1",
                                "inspection_time": "2026-05-01T08:20:00",
                                "inspection_lat": -26.2052,
                                "inspection_lon": 28.0490,
                                "behind_schedule_interval": "5-10 mins",
                            }
                        ],
                    },
                }
            ],
        }

        shift = ShiftCreate.model_validate(payload)

        self.assertTrue(shift.busses[0].license_disk_scan_succeeded)
        self.assertTrue(shift.busses[0].destination_displayed)
        self.assertTrue(shift.busses[0].inspections.external_inspected)
        self.assertTrue(shift.busses[0].inspections.internal_inspected)
        self.assertTrue(shift.busses[0].inspections.driver_inspected)
        self.assertTrue(shift.busses[0].inspections.passenger_counts_done)
        self.assertTrue(shift.busses[0].inspections.behind_schedule_reports_done)
        self.assertEqual(shift.busses[0].inspections.driver.driver_name, "Sipho Nkosi")
        self.assertEqual(
            shift.busses[0].inspections.passenger_counts[0].number_standing,
            8,
        )
        self.assertEqual(
            shift.busses[0].inspections.external.other.photos[0].photo,
            "damage-photo",
        )

    def test_group_bus_inspections_returns_nested_structure(self):
        timestamp = datetime(2026, 5, 1, 8, 0, 0)
        photo_created_at = datetime(2026, 5, 1, 8, 3, 0)

        def make_photo(photo_id, inspection_item, photo_value):
            return SimpleNamespace(
                id=photo_id,
                timestamp=timestamp,
                lat=-26.2045,
                lon=28.0480,
                inspection_item=inspection_item,
                photo=photo_value,
                created_at=photo_created_at,
            )

        def make_row(**overrides):
            values = {
                "id": 1,
                "shift_id": 10,
                "user_id": "firebase_uid_abc123",
                "bus_id": "VIN0001ZA",
                "fleet_number": "GA 01 001 GP",
                "internal_inspection_id": "insp-1",
                "inspection_type": "external",
                "inspection_time": timestamp,
                "inspection_lat": -26.2045,
                "inspection_lon": 28.0480,
                "pass_": True,
                "notes": None,
                "tyres_pass": None,
                "tyres_notes": None,
                "windows_pass": None,
                "windows_notes": None,
                "ext_other_pass": None,
                "ext_other_notes": None,
                "fire_extinguisher_present": None,
                "seats_pass": None,
                "seats_notes": None,
                "aisle_pass": None,
                "aisle_notes": None,
                "int_other_pass": None,
                "int_other_notes": None,
                "license_disk_scan_succeeded": None,
                "destination_displayed": None,
                "prdp_scan_succeeded": None,
                "prdp_expiry_date": None,
                "driver_identified": None,
                "driver_fail_reason": None,
                "driver_name": None,
                "count": 0,
                "number_seated": None,
                "number_standing": None,
                "behind_schedule_interval": None,
                "photos": [],
            }
            values.update(overrides)
            return SimpleNamespace(**values)

        rows = [
            make_row(
                id=1,
                inspection_type="external",
                license_disk_scan_succeeded=None,
                destination_displayed=None,
                tyres_pass=True,
                windows_pass=True,
                ext_other_pass=False,
                ext_other_notes="Body damage",
                photos=[make_photo(101, "ext_other", "damage-photo")],
            ),
            make_row(
                id=2,
                internal_inspection_id="insp-2",
                inspection_type="internal",
                fire_extinguisher_present=True,
                seats_pass=True,
                aisle_pass=True,
                int_other_pass=True,
            ),
            make_row(
                id=3,
                internal_inspection_id="insp-3",
                inspection_type="driver",
                license_disk_scan_succeeded=True,
                destination_displayed=True,
                prdp_scan_succeeded=True,
                driver_identified=True,
                driver_name="Sipho Nkosi",
            ),
            make_row(
                id=4,
                internal_inspection_id="insp-4",
                inspection_type="count",
                count=40,
                number_seated=32,
                number_standing=8,
            ),
            make_row(
                id=5,
                internal_inspection_id="insp-5",
                inspection_type="behind_schedule",
                behind_schedule_interval="5-10 mins",
            ),
        ]

        grouped = _group_bus_inspection_rows(rows)

        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["bus_id"], "VIN0001ZA")
        self.assertTrue(grouped[0]["license_disk_scan_succeeded"])
        self.assertTrue(grouped[0]["destination_displayed"])
        self.assertTrue(grouped[0]["inspections"]["external_inspected"])
        self.assertTrue(grouped[0]["inspections"]["internal_inspected"])
        self.assertTrue(grouped[0]["inspections"]["driver_inspected"])
        self.assertTrue(grouped[0]["inspections"]["passenger_counts_done"])
        self.assertTrue(grouped[0]["inspections"]["behind_schedule_reports_done"])
        self.assertEqual(grouped[0]["inspections"]["driver"]["driver_name"], "Sipho Nkosi")
        self.assertEqual(
            grouped[0]["inspections"]["external"]["other"]["photos"][0]["photo"],
            "damage-photo",
        )
        self.assertEqual(
            grouped[0]["inspections"]["passenger_counts"][0]["number_standing"],
            8,
        )
        self.assertEqual(
            grouped[0]["inspections"]["behind_schedule_reports"][0]["behind_schedule_interval"],
            "5-10 mins",
        )


if __name__ == "__main__":
    unittest.main()
