"""Exercise real persistence/readback without writing to the live database."""
import base64
import json
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.bus_inspection import BusInspection
from app.models.photo import DestinationDisplayPhoto, Photo, Selfie
from app.models.shift import Shift
from app.routers.inspection import inspection_router
from app.routers.monitors import monitor_router
from app.schemas.shift import BusIn, BusMetaIn


@pytest.fixture
def api():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})

    @event.listens_for(engine, 'connect')
    def schemas(connection, _):
        for name in ('shifts', 'inspections', 'photos'):
            connection.execute(f"ATTACH DATABASE ':memory:' AS {name}")

    with engine.begin() as connection:
        for model in (Shift, BusInspection, Photo, Selfie, DestinationDisplayPhoto):
            # SQLite needs INTEGER (not BIGINT) for generated primary keys.
            ddl = str(CreateTable(model.__table__).compile(engine)).replace('BIGINT', 'INTEGER')
            connection.exec_driver_sql(ddl)
    app = FastAPI()
    app.include_router(monitor_router, prefix='/shift')
    app.include_router(inspection_router, prefix='/inspection')
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: TokenData(sub='monitor-a', role='Monitor')
        with patch('app.routers.monitors.get_settings', return_value=SimpleNamespace(audit_success_payloads_enabled=False)):
            with TestClient(app) as client:
                yield client, db, app
    engine.dispose()


def payload():
    return dict(user_id='monitor-a', start_time='2026-09-14T08:00:00', end_time='2026-09-14T16:00:00',
                start_lat=-29.1, start_lon=26.2, end_lat=-29.1, end_lon=26.2,
                device_id='offline-device', selfies=[], busses=[bus()])


def bus(duty='504', replacement=False, displayed=False):
    return dict(bus_id='VIN-A', bus_number='FLEET-A', duty_number=duty, replacement_bus=replacement,
                destination_displayed=displayed, photos=[photo('first'), photo('second')], inspections={})


def photo(content):
    return dict(timestamp='2026-09-14T08:15:00', lat=-29.1, lon=26.2,
                photo=base64.b64encode(content.encode()).decode())


@pytest.mark.parametrize('model', [BusIn, BusMetaIn])
def test_old_payloads_can_omit_photos(model):
    data = bus()
    del data['photos']
    assert model.model_validate(data).photos == []


@pytest.mark.parametrize('displayed', [True, False, None])
def test_json_photo_only_bus_roundtrips_without_inspection_events(api, displayed):
    client, db, _ = api
    data = payload()
    data['busses'][0]['destination_displayed'] = displayed
    result = client.post('/shift/create_shift/', json=data)
    assert result.status_code == 201, result.text
    shift_id = result.json()['shift_id']
    assert db.scalar(select(func.count()).select_from(BusInspection)) == 0
    assert db.scalar(select(func.count()).select_from(Photo)) == 0
    assert db.scalar(select(func.count()).select_from(DestinationDisplayPhoto)) == 2
    response = client.get('/inspection/bus_inspections/by_shift_ids', params={'shift_ids': shift_id})
    assert response.status_code == 200, response.text
    group = response.json()[0]
    assert group['destination_displayed'] is displayed
    assert [p['photo'] for p in group['photos']] == [p['photo'] for p in data['busses'][0]['photos']]
    assert group['inspections']['external'] is None
    assert not group['inspections']['external_inspected']


def test_photos_are_not_duplicated_or_mixed_between_duties_and_replacements(api):
    client, db, _ = api
    data = payload()
    data['busses'] = [bus(), bus('505'), bus(replacement=True)]
    data['busses'][0]['inspections'] = {'passenger_counts': [
        dict(internal_inspection_id=f'count-{i}', inspection_time='2026-09-14T08:20:00',
             inspection_lat=-29.1, inspection_lon=26.2, number_seated=2, number_standing=0)
        for i in range(2)
    ]}
    response = client.post('/shift/create_shift/', json=data)
    assert response.status_code == 201, response.text
    groups = client.get('/inspection/bus_inspections').json()
    assert len(groups) == 3
    assert all(len(g['photos']) == 2 for g in groups)
    assert db.scalar(select(func.count()).select_from(BusInspection)) == 2
    assert db.scalar(select(func.count()).select_from(DestinationDisplayPhoto)) == 6
    assert len(client.get('/inspection/bus_inspections', params={'limit': 1}).json()) == 1
    assert len(client.get('/inspection/bus_inspections', params={'limit': 0}).json()) == 0


def test_photo_only_groups_respect_all_read_filters(api):
    client, _, _ = api
    assert client.post('/shift/create_shift/', json=payload()).status_code == 201
    assert len(client.get('/inspection/bus_inspections/by_bus_ids', params={'bus_ids': 'VIN-A'}).json()) == 1
    assert client.get('/inspection/bus_inspections/by_bus_ids', params={'bus_ids': 'VIN-B'}).status_code == 404
    assert len(client.get('/inspection/bus_inspections/by_user_ids', params={'user_ids': 'monitor-a'}).json()) == 1
    assert client.get('/inspection/bus_inspections/by_user_ids', params={'user_ids': 'monitor-b'}).status_code == 404
    assert client.get('/inspection/bus_inspections/by_shift_ids', params={'shift_ids': 999}).status_code == 404
    for params in ({'start_date': '2026-09-15'}, {'end_date': '2026-09-13'},
                   {'start_date': '2026-09-14', 'start_time': '09:00:00'},
                   {'end_date': '2026-09-14', 'end_time': '08:00:00'}):
        assert client.get('/inspection/bus_inspections', params=params).json() == []


def multipart_data():
    data = payload()
    files = {}
    for index, item in enumerate(data['busses'][0]['photos']):
        files[f'bus_0_destination_displayed_photo_{index}'] = ('photo.jpg', base64.b64decode(item.pop('photo')), 'image/jpeg')
    return data, files


def test_multipart_files_link_to_bus_question(api):
    client, db, _ = api
    data, files = multipart_data()
    response = client.post('/shift/create_shift_multipart/', data={'data': json.dumps(data)}, files=files)
    assert response.status_code == 201, response.text
    group = client.get('/inspection/bus_inspections').json()[0]
    assert [p['photo'] for p in group['photos']] == [photo('first')['photo'], photo('second')['photo']]
    assert db.scalar(select(func.count()).select_from(BusInspection)) == 0


def test_missing_multipart_destination_file_is_rejected(api):
    client, db, _ = api
    data, files = multipart_data()
    del files['bus_0_destination_displayed_photo_1']
    response = client.post('/shift/create_shift_multipart/', data={'data': json.dumps(data)}, files=files)
    assert response.status_code == 422, response.text
    assert response.json()['detail'] == 'Missing file: bus_0_destination_displayed_photo_1'
    assert db.scalar(select(func.count()).select_from(DestinationDisplayPhoto)) == 0


def test_later_bus_missing_file_rolls_back_earlier_bus_photos(api):
    client, db, _ = api
    data, files = multipart_data()
    data['busses'].append({**data['busses'][0], 'duty_number': '505'})
    response = client.post('/shift/create_shift_multipart/', data={'data': json.dumps(data)}, files=files)
    assert response.status_code == 422, response.text
    assert db.scalar(select(func.count()).select_from(DestinationDisplayPhoto)) == 0


def test_openapi_documents_bus_photo_array(api):
    schemas = api[2].openapi()['components']['schemas']
    for name, item in [('BusIn', 'PhotoIn'), ('GroupedBusInspectionResponse', 'InspectionItemPhotoResponse')]:
        schema = schemas[name]
        assert 'photos' not in schema['required']
        assert schema['properties']['photos']['items']['$ref'].endswith('/' + item)
