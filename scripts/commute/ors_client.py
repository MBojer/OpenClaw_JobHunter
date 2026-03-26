"""
scripts/commute/ors_client.py
OpenRouteService client for commute time calculation.
Uses self-hosted ORS instance — no API key required.

Supports: driving-car, cycling-regular, cycling-electric, foot-walking
Does NOT support public transport (on roadmap — use Rejseplanen API).

ORS docs: https://openrouteservice.org/dev/#/api-docs/v2/directions
"""
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ORS_BASE_URL = os.environ.get("ORS_BASE_URL", "").rstrip("/")

SUPPORTED_MODES = {
    "driving-car",
    "cycling-regular",
    "cycling-electric",
    "foot-walking",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class ORSError(Exception):
    pass


def get_coordinates(address: str) -> tuple[float, float] | None:
    """
    Geocode an address using Nominatim (OpenStreetMap).
    Returns (lon, lat) or None if not found.
    """
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    url = f"{NOMINATIM_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JobHunter/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        if not data:
            return None

        return (float(data[0]["lon"]), float(data[0]["lat"]))

    except Exception as e:
        raise ORSError(f"Geocoding failed for '{address}': {e}") from e


def get_commute_minutes(
    origin_coords: tuple[float, float],
    destination: str,
    mode: str = "driving-car",
) -> int | None:
    """
    Get commute time in minutes from origin to destination.

    Args:
        origin_coords: (lon, lat) of home address
        destination: job location string (geocoded internally)
        mode: ORS routing profile

    Returns:
        Minutes as int, or None if route not found / too far / error
    """
    if not ORS_BASE_URL:
        raise ORSError("ORS_BASE_URL not set in .env")

    if mode not in SUPPORTED_MODES:
        raise ORSError(f"Unsupported mode: {mode}. Use one of {SUPPORTED_MODES}")

    # Geocode destination
    dest_coords = get_coordinates(destination)
    if not dest_coords:
        return None

    origin_lon, origin_lat = origin_coords
    dest_lon, dest_lat = dest_coords

    url = (
        f"{ORS_BASE_URL}/ors/v2/directions/{mode}"
        f"?start={origin_lon},{origin_lat}"
        f"&end={dest_lon},{dest_lat}"
    )

    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/geo+json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        # Check for ORS error response
        if "error" in data:
            code = data["error"].get("code")
            if code == 2004:
                # Exceeds max distance — job is too far
                return None
            raise ORSError(data["error"].get("message", "ORS error"))

        features = data.get("features", [])
        if not features:
            return None

        summary = features[0]["properties"]["summary"]
        duration_seconds = summary["duration"]
        return round(duration_seconds / 60)

    except ORSError:
        raise
    except Exception as e:
        raise ORSError(f"Routing failed: {e}") from e


def get_best_commute(
    origin_coords: tuple[float, float],
    destination: str,
    modes: list[str],
) -> tuple[int | None, str | None]:
    """
    Try multiple transport modes and return the best (fastest) result.

    Returns:
        (minutes, mode) or (None, None) if all failed
    """
    best_minutes = None
    best_mode = None

    for mode in modes:
        if mode not in SUPPORTED_MODES:
            continue
        try:
            minutes = get_commute_minutes(origin_coords, destination, mode)
            if minutes is not None:
                if best_minutes is None or minutes < best_minutes:
                    best_minutes = minutes
                    best_mode = mode
        except ORSError:
            continue

    return best_minutes, best_mode


def is_available() -> bool:
    """Check if ORS instance is reachable."""
    if not ORS_BASE_URL:
        return False
    try:
        url = f"{ORS_BASE_URL}/ors/v2/health"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ready"
    except Exception:
        return False