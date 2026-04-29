"""
Update master_data.route_stop.gps_raw to a standardized DMS string
computed from the stored decimal-degree latitude/longitude values.

Output format: 28°13'37.6"S 28°18'17.1"E

Usage:
    .venv/bin/python scripts/normalize_gps_raw.py [--dry-run]
"""

import argparse
import os
import sys

import psycopg2

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = "fs_bus_api"
DB_USER = "fs_bus_user"
DB_PASSWORD = "HxiRuXrLB4yXkgRQrXEWJPOf9Ftkgpz0B4Wt0X4E0ehll8Z41ZVTe5MBsjmfIq0x"


def decimal_to_dms(value: float, is_lat: bool) -> str:
    """Convert decimal degrees to DMS string, e.g. 28°13'37.6"S"""
    abs_val = abs(value)
    degrees = int(abs_val)
    minutes_float = (abs_val - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60, 1)

    # Avoid 60.0 seconds due to rounding
    if seconds >= 60.0:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1

    if is_lat:
        direction = "S" if value < 0 else "N"
    else:
        direction = "W" if value < 0 else "E"

    return f"{degrees}\u00b0{minutes}'{seconds}\"{direction}"


def decimal_to_dms_pair(lat: float, lon: float) -> str:
    return f"{decimal_to_dms(lat, True)} {decimal_to_dms(lon, False)}"


def normalize(dry_run: bool = False) -> None:
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stop_id, latitude, longitude FROM master_data.route_stop "
                "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} stops with GPS coordinates.")

            updates = [
                (decimal_to_dms_pair(float(lat), float(lon)), stop_id)
                for stop_id, lat, lon in rows
            ]

            # Sample preview
            print("\nSample conversions:")
            for gps_raw, stop_id in updates[:5]:
                print(f"  stop_id={stop_id}  →  {gps_raw}")

            if not dry_run:
                psycopg2.extras.execute_batch(
                    cur,
                    "UPDATE master_data.route_stop SET gps_raw = %s WHERE stop_id = %s",
                    updates,
                    page_size=500,
                )
                conn.commit()
                print(f"\nUpdated {len(updates)} rows.")
            else:
                conn.rollback()
                print("\n[DRY RUN] No changes written.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import psycopg2.extras  # noqa: F811 — needed for execute_batch

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        normalize(dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
