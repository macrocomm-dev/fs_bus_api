"""Validate a timetable, or publish it atomically with --publish."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.departure_service import read_departures, publish_departures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--operator-id", type=int, required=True)
    parser.add_argument("--publish", action="store_true", help="Publish a new version; without this flag only validate the CSV")
    args = parser.parse_args()
    try:
        records = read_departures(args.csv)
        print(f"Validated {len(records)} departures.")
        if args.publish:
            from app.database import SessionLocal
            with SessionLocal.begin() as db:
                uid, changed = publish_departures(db, args.operator_id, records, args.csv.name)
            print(f"{'Published' if changed else 'Already current'} schedule {uid}.")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
