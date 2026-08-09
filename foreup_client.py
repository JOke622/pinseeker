"""
Client for ForeUp Software's public booking-times API.

This calls the same JSON endpoint the ForeUp booking widget itself calls
to render available tee times (no login required) - avoids brittle
DOM/Selenium scraping.

Each course can have several "booking classes" (rate tiers) with different
booking windows (e.g. a public 7-day window vs. a members-only 9-day one) -
the plain/default query (booking_class="") only gets the *shortest* one,
which silently truncates how far out results go. _best_booking_class() finds
the longest-window class that doesn't require login and uses that instead.
"""
import concurrent.futures
import re
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

_BOOKING_CLASS_RE = re.compile(
    r'"booking_class_id":"(\d+)".*?"name":"([^"]*)".*?'
    r'"online_booking_protected":"(\d)".*?"days_in_booking_window":"(\d+)"'
)
_DEFAULT_WINDOW_RE = re.compile(r'"days_in_booking_window":"(\d+)","default":"1"')
_COURSE_ID_RE = re.compile(r"/booking/(\d+)/")

_booking_class_cache = {}  # course id -> best booking_class string ("" if none better)


def _best_booking_class(course):
    """Find the public (non-login) booking class with the largest booking
    window for this course, if any beat the plain default. Cached per course
    for the life of the process; falls back to "" (default behavior) on any
    failure so a discovery hiccup never breaks the actual tee-time fetch.
    """
    if course["id"] in _booking_class_cache:
        return _booking_class_cache[course["id"]]

    best = ""
    try:
        match = _COURSE_ID_RE.search(course.get("booking_url", ""))
        course_num_id = match.group(1) if match else None
        if course_num_id:
            resp = requests.get(
                f"{course['base_url']}/index.php/booking/{course_num_id}/{course['schedule_id']}",
                headers={**HEADERS, "Accept": "text/html"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            text = resp.text

            default_match = _DEFAULT_WINDOW_RE.search(text)
            default_window = int(default_match.group(1)) if default_match else 0

            best_window = default_window
            for class_id, _name, protected, window in _BOOKING_CLASS_RE.findall(text):
                if protected == "0" and int(window) > best_window:
                    best_window = int(window)
                    best = class_id
    except Exception:  # noqa: BLE001 - discovery is best-effort, never fatal
        best = ""

    _booking_class_cache[course["id"]] = best
    return best


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
        "booking_class": _best_booking_class(course),
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
