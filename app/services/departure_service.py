"""Validate and publish complete operator timetables without editing history."""

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from uuid import UUID, uuid4

SOURCE_COLUMNS = ("duty_no", "departure", "origin", "destination", "direction", "valid_days", "bus_type")
CSV_COLUMNS = ("uid", "schedule_uid", "operator_id", *SOURCE_COLUMNS)


@dataclass(frozen=True, order=True)
class DepartureInput:
    duty_no: str
    departure: time
    origin: str
    destination: str
    direction: str
    valid_days: str
    bus_type: str

    def values(self) -> dict:
        return {column: getattr(self, column) for column in SOURCE_COLUMNS}


def read_departures(path: Path) -> list[DepartureInput]:
    """Reject ambiguous times and duplicate rows before touching the database."""
    records = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(SOURCE_COLUMNS):
            raise ValueError("CSV header must be: " + ",".join(SOURCE_COLUMNS))
        for line, row in enumerate(reader, start=2):
            if None in row or any(row.get(key) is None or not row[key].strip() for key in SOURCE_COLUMNS):
                raise ValueError(f"Line {line}: every column must contain a value; extra columns are not allowed")
            values = {key: row[key].strip() for key in SOURCE_COLUMNS}
            departure = values["departure"]
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", departure):
                raise ValueError(f"Line {line}: departure {departure!r} must be an unambiguous HH:MM time")
            values["departure"] = time.fromisoformat(departure)
            record = DepartureInput(**values)
            if record in seen:
                raise ValueError(f"Line {line}: duplicate departure")
            seen.add(record)
            records.append(record)
    if not records:
        raise ValueError("The timetable must contain at least one departure")
    return sorted(records)


def timetable_hash(records: list[DepartureInput]) -> str:
    content = json.dumps([row.values() for row in sorted(records)], default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def publish_departures(db, operator_id: int, records: list[DepartureInput], source_name: str) -> tuple[UUID, bool]:
    """Caller commits. Serialize publishers per operator and retain old versions."""
    from sqlalchemy import insert, select
    from app.models.departure import Departure, ScheduleVersion
    from app.models.master_data import Operator

    if not records:
        raise ValueError("Cannot publish an empty timetable")
    operator = db.scalar(select(Operator).where(Operator.operator_id == operator_id).with_for_update())
    if operator is None or not operator.is_active:
        raise ValueError("Operator does not exist or is inactive")
    current = db.scalar(select(ScheduleVersion).where(
        ScheduleVersion.operator_id == operator_id, ScheduleVersion.is_active.is_(True)
    ))
    digest = timetable_hash(records)
    if current is not None and current.content_sha256 == digest:
        return current.uid, False
    version_uid = uuid4()
    version = ScheduleVersion(
        uid=version_uid, operator_id=operator_id, source_name=source_name,
        content_sha256=digest, row_count=len(records), is_active=False,
    )
    db.add(version)
    db.flush()
    # Batch multi-value INSERTs to avoid one network round trip per departure.
    for offset in range(0, len(records), 500):
        values = [dict(uid=uuid4(), schedule_uid=version_uid, **row.values()) for row in records[offset:offset + 500]]
        db.execute(insert(Departure).values(values))
    if current is not None:
        current.is_active = False
        db.flush()
    version.is_active = True
    db.flush()
    return version_uid, True


def render_departures_csv(rows) -> bytes:
    from app.schemas.departure import DepartureCsvRow

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        values = {column: getattr(row, column) for column in CSV_COLUMNS}
        values["departure"] = row.departure.strftime("%H:%M")
        validated = DepartureCsvRow.model_validate(values).model_dump(mode="json")
        writer.writerow([validated[column] for column in CSV_COLUMNS])
    return output.getvalue().encode("utf-8")
