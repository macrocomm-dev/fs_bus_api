"""Smart Fleet / GPSWOX API helpers used by backend endpoints."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

import requests

from app.config import Settings

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
_MAX_ADDRESS_WORKERS = 8


@dataclass(frozen=True)
class SmartFleetVehiclePosition:
    """Latest Smart Fleet position snapshot for one tracked object."""

    smart_fleet_device_id: int | None
    last_address: str | None
    last_response_time: datetime | None


def normalize_vehicle_identifier(value: object) -> str | None:
    """Normalize vehicle identifiers so VIN, reg and fleet values can be matched."""

    if value is None:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]", "", str(value)).lower()
    return normalized or None


def vehicle_identifier_keys(*values: object) -> set[str]:
    """Return normalized keys for complete values and useful tokens within them."""

    keys: set[str] = set()
    for value in values:
        if value is None:
            continue
        normalized = normalize_vehicle_identifier(value)
        if normalized:
            keys.add(normalized)
        for token in _TOKEN_PATTERN.findall(str(value)):
            token_key = normalize_vehicle_identifier(token)
            if token_key and len(token_key) >= 3:
                keys.add(token_key)
    return keys


def get_latest_vehicle_positions(
    settings: Settings,
) -> dict[str, SmartFleetVehiclePosition]:
    """Fetch latest Smart Fleet object positions keyed by normalized vehicle identifiers."""

    if not settings.smart_fleet_base_url or not settings.smart_fleet_api_hash:
        logger.warning("Smart Fleet position lookup skipped because configuration is incomplete.")
        return {}

    url = f"{settings.smart_fleet_base_url.rstrip('/')}/api/get_devices_latest"
    try:
        response = requests.get(
            url,
            params={"lang": "en", "user_api_hash": settings.smart_fleet_api_hash},
            headers={"Accept": "application/json"},
            timeout=20,
        )
        if response.status_code >= 400:
            logger.warning(
                "Smart Fleet latest-device request was rejected: status=%s body_prefix=%r",
                response.status_code,
                response.text[:300],
            )
            return {}
        payload = response.json()
    except requests.RequestException:
        logger.exception("Smart Fleet latest-device request failed.")
        return {}
    except ValueError:
        logger.exception("Smart Fleet latest-device response was not valid JSON.")
        return {}

    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        logger.warning("Smart Fleet latest-device response did not contain an items list.")
        return {}

    entries: list[
        tuple[
            set[str],
            int | None,
            str | None,
            datetime | None,
            float | None,
            float | None,
        ]
    ] = []
    coordinates_needing_address: set[tuple[float, float]] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        device_data = item.get("device_data")
        if not isinstance(device_data, dict):
            device_data = {}

        keys = vehicle_identifier_keys(
            item.get("name"),
            device_data.get("name"),
            device_data.get("vin"),
            device_data.get("registration_number"),
            device_data.get("plate_number"),
        )
        if not keys:
            continue

        latitude = _coerce_float(item.get("lat"))
        longitude = _coerce_float(item.get("lng"))
        address = _coerce_address(item.get("address"))
        if address is None and latitude is not None and longitude is not None:
            coordinates_needing_address.add((latitude, longitude))

        entries.append(
            (
                keys,
                _coerce_int(item.get("id")),
                address,
                _parse_smartfleet_datetime(item.get("time") or item.get("timestamp")),
                latitude,
                longitude,
            )
        )

    resolved_addresses = _resolve_addresses(
        settings=settings,
        coordinates=coordinates_needing_address,
    )

    positions: dict[str, SmartFleetVehiclePosition] = {}
    for keys, device_id, address, response_time, latitude, longitude in entries:
        resolved_address = address
        if resolved_address is None and latitude is not None and longitude is not None:
            resolved_address = resolved_addresses.get((latitude, longitude))
        if resolved_address is None and latitude is not None and longitude is not None:
            resolved_address = _format_coordinates(latitude, longitude)

        position = SmartFleetVehiclePosition(
            smart_fleet_device_id=device_id,
            last_address=resolved_address,
            last_response_time=response_time,
        )
        for key in keys:
            positions[key] = position

    return positions


def _resolve_addresses(
    settings: Settings, coordinates: set[tuple[float, float]]
) -> dict[tuple[float, float], str]:
    """Reverse-geocode coordinates through Smart Fleet's plain-text address endpoint."""

    if not coordinates:
        return {}

    resolved: dict[tuple[float, float], str] = {}
    worker_count = min(_MAX_ADDRESS_WORKERS, len(coordinates))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_coordinate = {
            executor.submit(_fetch_address, settings, latitude, longitude): (
                latitude,
                longitude,
            )
            for latitude, longitude in coordinates
        }
        for future in as_completed(future_to_coordinate):
            coordinate = future_to_coordinate[future]
            try:
                address = future.result()
            except Exception:  # noqa: BLE001 - keep vehicle list resilient.
                logger.exception("Smart Fleet address lookup failed.")
                continue
            if address:
                resolved[coordinate] = address

    return resolved


def _fetch_address(settings: Settings, latitude: float, longitude: float) -> str | None:
    return _fetch_address_cached(
        settings.smart_fleet_base_url.rstrip("/"),
        settings.smart_fleet_api_hash,
        f"{latitude:.4f}",
        f"{longitude:.4f}",
    )


@lru_cache(maxsize=2048)
def _fetch_address_cached(
    base_url: str, user_api_hash: str, latitude: str, longitude: str
) -> str | None:
    url = f"{base_url}/api/address"
    try:
        response = requests.get(
            url,
            params={
                "lang": "en",
                "user_api_hash": user_api_hash,
                "lat": latitude,
                "lng": longitude,
            },
            headers={"Accept": "text/plain,application/json"},
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Smart Fleet address request failed for coordinates %s, %s.",
            latitude,
            longitude,
        )
        return None

    return _coerce_address(response.text)


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_address(value: Any) -> str | None:
    text = _coerce_str(value)
    if text is None or text == "-":
        return None
    return text


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_coordinates(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f}, {longitude:.6f}"


def _parse_smartfleet_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OSError, OverflowError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None
