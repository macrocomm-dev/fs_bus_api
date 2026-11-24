from types import SimpleNamespace
from datetime import datetime, time
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi import HTTPException

from app.services.passenger_capacity import passenger_assessment, vehicle_capacity, inspection_pass
from app.routers.monitors import _passenger_count_record, _behind_schedule_record
from app.routers.inspection import _group_bus_inspection_rows
from app.schemas.shift import BusIn, BehindScheduleReportIn, BehindScheduleReportMetaIn, PassengerCountIn
from app.models.bus_inspection import BusInspection


@pytest.mark.parametrize('fleet,seats,standing', [('3000',65,12),('3999',65,12),('4000',114,32),('4513',114,32),('5000',79,24),('5999',79,24),('7000',49,12),('7999',49,12)])
def test_capacity_boundaries(fleet, seats, standing):
    assert vehicle_capacity(fleet) == (seats, standing)
    assert passenger_assessment(fleet, seats, standing)['pass_'] is True
    assert passenger_assessment(fleet, seats, standing + 1)['overloaded_passengers'] == 1
    assert passenger_assessment(fleet, seats + 1, 0)['pass_'] is False
    assert passenger_assessment(fleet, 0, standing + 1)['pass_'] is False
    assert passenger_assessment(fleet, seats + 2, standing + 3)['overloaded_passengers'] == 5


@pytest.mark.parametrize('fleet', [None, '', '2001', '300', '30000', 'VIN3001', 'GA 01 001 GP'])
def test_unknown_fleet_is_not_assessed(fleet):
    result = passenger_assessment(fleet, 100, 100)
    assert result['pass_'] is None
    assert result['overloaded_passengers'] is None


def test_missing_counts_do_not_imply_compliance():
    assert passenger_assessment('3002', None, 50)['pass_'] is None
    assert passenger_assessment('3002', 70, None)['pass_'] is None


def test_legacy_stored_pass_does_not_override_capacity():
    row = SimpleNamespace(inspection_type='count', fleet_number='3002', number_seated=65, number_standing=12, pass_=False)
    assert inspection_pass(row) is True
    row.number_standing = 13
    row.pass_ = True
    assert inspection_pass(row) is False


def bus():
    return BusIn(bus_number='3002', duty_number='504', inspections={})


def event():
    return dict(internal_inspection_id='event-1', inspection_time='2026-11-24T09:00:00', inspection_lat=-29.1, inspection_lon=26.2)


def test_count_write_and_grouped_read_agree():
    record, _ = _passenger_count_record(None, 1, 'monitor', bus(), PassengerCountIn(**event(), number_seated=65, number_standing=13))
    assert record['pass_'] is False
    assert record['count'] == 78
    row = BusInspection(id=1, **record)
    row.photos = []
    grouped = _group_bus_inspection_rows([row])[0]['inspections']['passenger_counts'][0]
    assert grouped['seating_capacity'] == 65
    assert grouped['standing_capacity'] == 12
    assert grouped['overloaded_passengers'] == 1
    assert grouped['pass_'] is False


@pytest.mark.parametrize('model', [BehindScheduleReportIn, BehindScheduleReportMetaIn])
def test_departure_time_snapshot_and_readback(model):
    uid = uuid4()
    data = model(**event(), behind_schedule_interval='6-15 mins late', departure_uid=uid, actual_departure_time='2026-11-24T08:10:00')
    db = Mock()
    db.get.return_value = SimpleNamespace(duty_no='504', departure=time(8, 0))
    record, _ = _behind_schedule_record(db, 1, 'monitor', bus(), data)
    assert record['scheduled_departure_time'] == time(8, 0)
    assert record['actual_departure_time'] == datetime(2026,11,24,8,10)
    assert record['actual_departure_time'] != data.inspection_time
    row = BusInspection(id=1, **record)
    row.photos = []
    result = _group_bus_inspection_rows([row])[0]['inspections']['behind_schedule_reports'][0]
    assert result['departure_uid'] == uid
    assert result['scheduled_departure_time'] == time(8,0)
    assert result['actual_departure_time'] == datetime(2026,11,24,8,10)


def test_old_reports_do_not_gain_invented_departure_times():
    report = BehindScheduleReportIn(**event(), behind_schedule_interval='0-5 mins')
    record, _ = _behind_schedule_record(None, 1, 'monitor', bus(), report)
    assert record['scheduled_departure_time'] is None
    assert record['actual_departure_time'] is None


@pytest.mark.parametrize('departure', [None, SimpleNamespace(duty_no='999', departure=time(8))])
def test_wrong_departure_is_rejected(departure):
    db = Mock()
    db.get.return_value = departure
    report = BehindScheduleReportIn(**event(), behind_schedule_interval='0-5 mins', departure_uid=uuid4())
    with pytest.raises(HTTPException) as error:
        _behind_schedule_record(db, 1, 'monitor', bus(), report)
    assert error.value.status_code == 422
