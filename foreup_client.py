"""
Client for ForeUp Software's public booking-times API.

This calls the same JSON endpoint the ForeUp booking widget itself calls
to render available tee times (no login required) - avoids brittle
DOM/Selenium scraping.
"""
import concurrent.futures
from datetime import datetime

import requests

API_KEY = "no_limits"
REQUEST_TIMEOUT_SECONDS = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _normalize_entry(course, entry):
    time_str = entry.get("time")
    try:
        parsed = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        hour_12 = parsed.hour % 12 or 12
        display_time = f"{hour_12}:{parsed.minute:02d} {'AM' if parsed.hour < 12 else 'PM'}"
    except (TypeError, ValueError):
        parsed = None
        display_time = time_str

    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": time_str,
        "display_time": display_time,
        "sort_key": parsed.isoformat() if parsed else time_str,
        "holes": entry.get("holes"),
        "available_spots": entry.get("available_spots"),
        "max_players": entry.get("maximum_players_per_booking"),
        "price_18": entry.get("green_fee_18"),
        "price_9": entry.get("green_fee_9"),
        "cart_fee_18": entry.get("cart_fee_18"),
        "cart_fee_9": entry.get("cart_fee_9"),
        "requires_credit_card": entry.get("require_credit_card") not in (None, "0", 0, "no"),
        "booking_url": course.get("booking_url"),
    }


def fetch_course_tee_times(course, date_str, holes="all", players=0):
    """date_str must be MM-DD-YYYY. Returns a dict with course + tee_times or error."""
    url = f"{course['base_url']}/index.php/api/booking/times"
    params = {
        "time": "all",
        "date": date_str,
        "holes": holes,
        "players": players,
        "booking_class": "",
        "schedule_id": course["schedule_id"],
        "specials_only": 0,
        "api_key": API_KEY,
    }

    try:
        response = requests.get(
            url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        raw_entries = response.json()
        if not isinstance(raw_entries, list):
            raise ValueError(f"Unexpected response shape: {type(raw_entries)}")
    except Exception as exc:  # noqa: BLE001 - surface any failure per-course
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": str(exc),
            "tee_times": [],
        }

    tee_times = [_normalize_entry(course, entry) for entry in raw_entries]
    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "error": None,
        "tee_times": tee_times,
    }


def fetch_all_tee_times(courses, date_str, holes="all", players=0):
    """Fetch tee times for every course in parallel, return combined + per-course results."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(courses) or 1) as pool:
        futures = [
            pool.submit(fetch_course_tee_times, course, date_str, holes, players)
            for course in courses
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    return results
