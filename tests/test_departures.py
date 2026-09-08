import csv
import io
import os
from datetime import time

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import TokenData, get_current_user
from app.database import get_db
from app.models.departure import Departure, ScheduleVersion
from app.models.master_data import Operator
from app.routers.routes import routes_router
from app.services.departure_service import DepartureInput, SOURCE_COLUMNS, publish_departures, read_departures


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def attach_schemas(connection, _):
        connection.execute("ATTACH DATABASE ':memory:' AS master_data")
        connection.execute("ATTACH DATABASE ':memory:' AS routes")

    for table in (Operator.__table__, ScheduleVersion.__table__, Departure.__table__):
        table.create(engine)
    with Session(engine) as session:
        session.add_all([Operator(operator_id=1, operator_name="IBL"), Operator(operator_id=2, operator_name="Maluti")])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def api(db):
    app = FastAPI()
    app.include_router(routes_router, prefix="/routes")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: TokenData(sub="monitor", role="Monitor")
    with TestClient(app) as client:
        yield app, client


def departure(duty="504", hour=4):
    return DepartureInput(duty, time(hour, 40), 'Rank, "A"', "Central Park – terminus", "Forward", "Monday to Friday", "Standard")


def publish(db, rows, operator=1):
    result = publish_departures(db, operator, rows, "test.csv")
    db.commit()
    return result


def test_csv_authentication_required(api):
    app, client = api
    del app.dependency_overrides[get_current_user]
    assert client.get("/routes/departures.csv").status_code == 401


def test_openapi_describes_csv_query_headers_and_empty_304(api):
    operation = api[0].openapi()["paths"]["/routes/departures.csv"]["get"]
    assert "requestBody" not in operation
    parameters = {p["name"]: p for p in operation["parameters"]}
    assert parameters["operator_id"]["in"] == "query"
    assert parameters["if-none-match"]["in"] == "header"
    assert operation["security"] == [{"HTTPBearer": []}]
    ok = operation["responses"]["200"]
    assert set(ok["content"]) == {"text/csv"}
    for response in (ok, operation["responses"]["304"]):
        assert {"ETag", "Cache-Control"} <= response["headers"].keys()
    assert "content" not in operation["responses"]["304"]
    assert "application/json" in operation["responses"]["401"]["content"]
    assert "application/json" in operation["responses"]["422"]["content"]
    row_schema = operation["x-csv-row-schema"]
    assert row_schema["properties"]["uid"]["format"] == "uuid"
    example = list(csv.DictReader(io.StringIO(ok["content"]["text/csv"]["example"])))[0]
    from app.schemas.departure import DepartureCsvRow
    assert DepartureCsvRow.model_validate(example).departure == "04:40"


def test_csv_roundtrip_identifiers_times_and_operator_filter(db, api):
    version, _ = publish(db, [departure()])
    publish(db, [departure("200")], operator=2)
    response = api[1].get("/routes/departures.csv?operator_id=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    row = rows[0]
    assert row["uid"] == str(db.scalar(select(Departure.uid).where(Departure.schedule_uid == version)))
    assert row["schedule_uid"] == str(version)
    assert row["operator_id"] == "1"
    assert row["departure"] == "04:40"
    assert row["origin"] == 'Rank, "A"'
    assert row["destination"] == "Central Park – terminus"
    assert len(list(csv.DictReader(io.StringIO(api[1].get("/routes/departures.csv").text)))) == 2


def test_update_retains_history_changes_etag_and_exports_only_current(db, api):
    old, _ = publish(db, [departure()])
    first = api[1].get("/routes/departures.csv")
    etag = first.headers["etag"]
    for value in (etag, f'"other", W/{etag}', "*"):
        cached = api[1].get("/routes/departures.csv", headers={"If-None-Match": value})
        assert cached.status_code == 304
        assert cached.content == b""
    new, _ = publish(db, [departure(hour=5)])
    updated = api[1].get("/routes/departures.csv", headers={"If-None-Match": etag})
    assert updated.status_code == 200
    assert updated.headers["etag"] != etag
    assert db.get(ScheduleVersion, old).is_active is False
    assert db.get(ScheduleVersion, new).is_active is True
    assert len(db.scalars(select(Departure)).all()) == 2
    rows = list(csv.DictReader(io.StringIO(updated.text)))
    assert len(rows) == 1 and rows[0]["departure"] == "05:40"


def test_reimport_identical_content_keeps_version_and_departure_uids(db):
    original, changed = publish(db, [departure(), departure("539")])
    before = set(db.scalars(select(Departure.uid)))
    repeated, changed_again = publish(db, [departure("539"), departure()])
    assert changed and not changed_again
    assert repeated == original
    assert set(db.scalars(select(Departure.uid))) == before


def test_failed_import_rolls_back_and_keeps_previous_timetable(db):
    old, _ = publish(db, [departure()])
    with pytest.raises(IntegrityError):
        publish_departures(db, 1, [departure("539"), departure("539")], "duplicate.csv")
    db.rollback()
    assert db.get(ScheduleVersion, old).is_active
    assert len(db.scalars(select(ScheduleVersion)).all()) == 1
    assert len(db.scalars(select(Departure)).all()) == 1


def test_unknown_operator_cannot_publish(db):
    with pytest.raises(ValueError, match="Operator"):
        publish_departures(db, 999, [departure()], "test.csv")


def test_empty_download_and_invalid_operator_parameter(api):
    response = api[1].get("/routes/departures.csv")
    assert response.status_code == 200
    assert list(csv.DictReader(io.StringIO(response.text))) == []
    assert api[1].get("/routes/departures.csv?operator_id=0").status_code == 422


@pytest.mark.parametrize("value", ["04:4", "24:00", "04:60", "", "04:40:01"])
def test_csv_import_rejects_invalid_times(tmp_path, value):
    path = tmp_path / "schedule.csv"
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(SOURCE_COLUMNS)
        writer.writerow(["504", value, "A", "B", "Forward", "Monday to Friday", "Standard"])
    with pytest.raises(ValueError):
        read_departures(path)


def test_csv_import_accepts_bom_and_leading_zero_duty(tmp_path):
    path = tmp_path / "schedule.csv"
    path.write_text(
        ",".join(SOURCE_COLUMNS) + '\n005,04:40,"Rank, A",B,Forward,Saturday,Train\n', encoding="utf-8-sig"
    )
    rows = read_departures(path)
    assert rows[0].duty_no == "005"
    assert rows[0].departure == time(4, 40)
    assert rows[0].origin == "Rank, A"


def test_csv_import_rejects_empty_or_duplicate_timetable(tmp_path):
    path = tmp_path / "schedule.csv"
    header = ",".join(SOURCE_COLUMNS) + "\n"
    path.write_text(header)
    with pytest.raises(ValueError, match="at least one"):
        read_departures(path)
    row = "504,04:40,A,B,Forward,Saturday,Standard\n"
    path.write_text(header + row + row)
    with pytest.raises(ValueError, match="duplicate"):
        read_departures(path)
