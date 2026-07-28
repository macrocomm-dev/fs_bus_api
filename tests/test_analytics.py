import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GCS_BUCKET_NAME", "test")

from app.routers.analytics import _event_type as analytics_event_type
from app.routers.vehicle import _event_type as vehicle_event_type


class AnalyticsTests(unittest.TestCase):
    def test_event_id_99_is_speeding(self):
        self.assertEqual(analytics_event_type(99), "Speeding")
        self.assertEqual(vehicle_event_type(99), "Speeding")

    def test_unknown_event_id_uses_generic_label(self):
        self.assertEqual(analytics_event_type(42), "Event 42")
        self.assertEqual(vehicle_event_type(42), "Event 42")
