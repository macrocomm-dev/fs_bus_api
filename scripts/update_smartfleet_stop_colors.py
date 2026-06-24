"""Bulk-update Smart Fleet geozone colors for a target geofence group.

Default behavior previews the affected geozones. Pass ``--apply`` to perform
the updates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


DEFAULT_BASE_URL = "https://smart-fleet.co.za"
DEFAULT_GROUP_ID = 18
DEFAULT_COLOR = "#ff9b00"
DEFAULT_CONCURRENCY = 12


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def build_api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/api/{path.lstrip('/')}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-update Smart Fleet geofence colors for a group."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--group-id", type=int, default=DEFAULT_GROUP_ID)
    parser.add_argument("--color", default=DEFAULT_COLOR)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the updates. Without this flag, the script only previews.",
    )
    return parser.parse_args()


def get_geofences(base_url: str, api_hash: str) -> list[dict]:
    response = httpx.get(
        build_api_url(base_url, "get_geofences"),
        params={"lang": "en", "user_api_hash": api_hash},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("items", {}).get("geofences", [])


async def update_geofence_color(
    client: httpx.AsyncClient,
    base_url: str,
    api_hash: str,
    geofence_id: int,
    color: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int, bool, str | None]:
    async with semaphore:
        response = await client.post(
            build_api_url(base_url, "edit_geofence"),
            params={"lang": "en", "user_api_hash": api_hash},
            json={"id": geofence_id, "polygon_color": color},
        )
        response.raise_for_status()
        payload = response.json()
        success = payload.get("status") == 1
        message = payload.get("message") if isinstance(payload, dict) else None
        return geofence_id, success, message


async def apply_updates(
    geofences: list[dict],
    base_url: str,
    api_hash: str,
    color: str,
    concurrency: int,
) -> list[tuple[int, bool, str | None]]:
    semaphore = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            update_geofence_color(
                client=client,
                base_url=base_url,
                api_hash=api_hash,
                geofence_id=int(geofence["id"]),
                color=color,
                semaphore=semaphore,
            )
            for geofence in geofences
        ]
        return await asyncio.gather(*tasks)


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)

    api_hash = os.getenv("SMART_FLEET_API_HASH")
    base_url = args.base_url or os.getenv("SMART_FLEET_BASE_URL", DEFAULT_BASE_URL)
    if not api_hash:
        print("ERROR: SMART_FLEET_API_HASH is not set.", file=sys.stderr)
        return 1

    geofences = get_geofences(base_url, api_hash)
    matching = [g for g in geofences if int(g.get("group_id") or 0) == args.group_id]

    if not matching:
        print(f"No geofences found for group_id={args.group_id}.")
        return 1

    already_target = [
        g for g in matching if str(g.get("polygon_color", "")).lower() == args.color.lower()
    ]
    needs_update = [g for g in matching if g not in already_target]

    print(
        f"Found {len(matching)} geofences in group_id={args.group_id}. "
        f"{len(already_target)} already use {args.color}. "
        f"{len(needs_update)} need updates."
    )
    print("Sample names:")
    for geofence in matching[:10]:
        print(
            f"  id={geofence['id']} name={geofence['name']} color={geofence.get('polygon_color')}"
        )

    if not args.apply:
        print("\nDry run only. Re-run with --apply to update Smart Fleet.")
        return 0

    if not needs_update:
        print("No updates needed.")
        return 0

    print(f"\nUpdating {len(needs_update)} geofences to {args.color} ...")
    results = asyncio.run(
        apply_updates(
            geofences=needs_update,
            base_url=base_url,
            api_hash=api_hash,
            color=args.color,
            concurrency=args.concurrency,
        )
    )

    failures = [result for result in results if not result[1]]
    print(f"Updated {len(results) - len(failures)} geofences.")
    if failures:
        print("Failures:")
        for geofence_id, _, message in failures[:20]:
            print(f"  id={geofence_id} message={message}")
        return 1

    refreshed = get_geofences(base_url, api_hash)
    refreshed_matching = [
        g for g in refreshed if int(g.get("group_id") or 0) == args.group_id
    ]
    not_updated = [
        g
        for g in refreshed_matching
        if str(g.get("polygon_color", "")).lower() != args.color.lower()
    ]
    if not_updated:
        print(
            f"Verification failed: {len(not_updated)} geofences do not have color {args.color}."
        )
        print(json.dumps(not_updated[:5], indent=2)[:2000])
        return 1

    print(
        f"Verification passed: all {len(refreshed_matching)} geofences in group_id={args.group_id} now use {args.color}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())