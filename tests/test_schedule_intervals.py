from datetime import datetime
from types import SimpleNamespace

import pytest

from app.routers.analytics import _route_start_interval_counts, _route_start_summary_items
from app.routers.monitors import _behind_schedule_interval_repairs_from_payload, _behind_schedule_record
from app.schemas.shift import BehindScheduleInterval, BehindScheduleReportIn, BehindScheduleReportMetaIn
from app.services.schedule_intervals import LATE_ROUTE_START_INTERVALS, MAJOR_DELAY_INTERVALS


CURRENT = ['Early departure', '0-5 mins', '6-15 mins late', '15-30 mins late', '30+ mins late']
LEGACY = ['5-10 mins', '10-15 mins', '15+ mins']


def report_payload(value):
    return dict(
        internal_inspection_id='schedule-check', inspection_time='2026-09-14T08:00:00',
        inspection_lat=-29.1, inspection_lon=26.2, behind_schedule_interval=value,
    )


@pytest.mark.parametrize('model', [BehindScheduleReportIn, BehindScheduleReportMetaIn])
@pytest.mark.parametrize('value', CURRENT + LEGACY)
def test_json_and_multipart_preserve_current_and_offline_legacy_values(model, value):
    report = model.model_validate(report_payload(value))
    assert report.model_dump(mode='json')['behind_schedule_interval'] == value
    bus = SimpleNamespace(bus_id='TESTVIN', bus_number='504', duty_number='504', replacement_bus=False,
                          license_disk_scan_succeeded=True, destination_displayed=True)
    record, _ = _behind_schedule_record(None, 123, 'monitor', bus, report)
    assert record['behind_schedule_interval'] == value
    assert record['inspection_type'] == 'behind_schedule'
    assert record['inspection_time'] == datetime(2026, 9, 14, 8)
    raw = {'busses': [{'inspections': {'behind_schedule_reports': [report_payload(value)]}}]}
    assert _behind_schedule_interval_repairs_from_payload(raw) == []


@pytest.mark.parametrize('value', ['', 'not-a-band', [], {}])
def test_existing_invalid_value_fallback_remains_audited(value):
    report = BehindScheduleReportIn.model_validate(report_payload(value))
    assert report.behind_schedule_interval == '0-5 mins'
    raw = {'busses': [{'inspections': {'behind_schedule_reports': [report_payload(value)]}}]}
    repairs = _behind_schedule_interval_repairs_from_payload(raw)
    assert len(repairs) == 1 and repairs[0]['original_value'] == value
    assert repairs[0]['defaulted_to'] == '0-5 mins'


def test_early_checks_reduce_on_time_percentage_but_are_not_late():
    assert _route_start_interval_counts({
        'Early departure': 4, '0-5 mins': 10, '6-15 mins late': 3,
        '15-30 mins late': 2, '30+ mins late': 1, 'Unknown': 99,
    }) == (10, 6, 20)
    assert _route_start_interval_counts({'Early departure': 5}) == (0, 0, 5)
    assert 'Early departure' not in LATE_ROUTE_START_INTERVALS
    assert '0-5 mins' not in LATE_ROUTE_START_INTERVALS
    assert MAJOR_DELAY_INTERVALS <= LATE_ROUTE_START_INTERVALS
    assert '6-15 mins late' not in MAJOR_DELAY_INTERVALS


def test_legacy_counts_keep_their_original_meaning_and_are_visible_when_present():
    counts = {'0-5 mins': 10, '5-10 mins': 4, '10-15 mins': 2, '15+ mins': 1}
    assert _route_start_interval_counts(counts) == (10, 7, 17)
    items = {item.drill_key: item for item in _route_start_summary_items(counts)}
    assert items['behind-schedule-early'].value == 0
    assert items['behind-schedule-0-5'].value == 10
    assert items['behind-schedule-6-15'].value == 0
    assert items['behind-schedule-15-30'].value == 0
    assert items['behind-schedule-30-plus'].value == 0
    assert items['behind-schedule-15-plus'].value == 1
    assert 'legacy' in items['behind-schedule-15-plus'].label
    assert items[None].value == 7
    current_only = _route_start_summary_items({'30+ mins late': 2})
    assert not any('legacy' in item.label for item in current_only)


def test_openapi_advertises_new_and_offline_compatible_values():
    from app.main import app
    enum = app.openapi()['components']['schemas']['BehindScheduleInterval']['enum']
    assert enum == CURRENT + LEGACY
    assert {member.value for member in BehindScheduleInterval} == set(enum)
