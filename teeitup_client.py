"""
Client for TeeItUp/Lightspeed Golf's booking widget API (book.teeitup.com / play.teeitup.com).

Simpler than Club Prophet or ForeUp - a single public GET call, no auth at all:
    GET https://phx-api-be-east-1b.kenna.io/v2/tee-times?date={YYYY-MM-DD}
    Header: x-be-alias: {site subdomain, e.g. "butternut-farm-golf-club"}

The x-be-alias header alone scopes results to that site's own facility, so
"facility_id" in courses.py is optional - only needed if a course ever turns
out to host more than one facility under the same alias.

Times in the response are UTC and need converting to the course's local time zone.
"""
import concurrent.futures
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

REQUEST_TIMEOUT_SECONDS = 10
API_BASE = "https://phx-api-be-east-1b.kenna.io"
HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
DEFAULT_TIMEZONE = "America/New_York"


def _price_for(rates, hole_count):
    for rate in rates:
        if rate.get("holes") == hole_count:
            cents = rate.get("greenFeeWalking")
            if cents is None:
                cents = rate.get("greenFeeCart")
            if cents is not None:
                return round(cents / 100)
    return None


def _normalize_entry(course, entry):
    time_str = entry.get("teetime")
    try:
        parsed_utc = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=ZoneInfo("UTC")
        )
        parsed_local = parsed_utc.astimezone(ZoneInfo(course.get("timezone", DEFAULT_TIMEZONE)))
        hour_12 = parsed_local.hour % 12 or 12
        display_time = f"{hour_12}:{parsed_local.minute:02d} {'AM' if parsed_local.hour < 12 else 'PM'}"
        sort_key = parsed_local.isoformat()
    except (TypeError, ValueError):
        display_time = time_str
        sort_key = time_str or ""

    rates = entry.get("rates") or []
    holes = rates[0].get("holes") if rates else None
    max_players = entry.get("maxPlayers") or 0
    booked = entry.get("bookedPlayers") or 0

    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": time_str,
        "display_time": display_time,
        "sort_key": sort_key,
        "holes": holes,
        "available_spots": max(max_players - booked, 0),
        "max_players": max_players,
        "price_18": _price_for(rates, 18),
        "price_9": _price_for(rates, 9),
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": course.get("booking_url"),
    }


def fetch_course_tee_times(course, date_str):
    """course: dict with id, name, alias (site subdomain), booking_url, optional facility_id.
    date_str must be YYYY-MM-DD.
    """
    params = {"date": date_str}
    if course.get("facility_id"):
        params["facilityIds"] = course["facility_id"]

    try:
        resp = requests.get(
            f"{API_BASE}/v2/tee-times",
            params=params,
            headers={**HEADERS_BASE, "x-be-alias": course["alias"]},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        days = resp.json()
        entries = []
        for day in days:
            entries.extend(day.get("teetimes") or [])
    except Exception as exc:  # noqa: BLE001 - surface any failure per-course
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": str(exc),
            "tee_times": [],
        }

    tee_times = [_normalize_entry(course, e) for e in entries]
    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "error": None,
        "tee_times": tee_times,
    }


def fetch_all_tee_times(courses, date_str):
    if not courses:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(courses)) as pool:
        futures = [pool.submit(fetch_course_tee_times, c, date_str) for c in courses]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results
