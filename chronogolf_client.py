"""
Client for Chronogolf's (Lightspeed Golf) public marketplace widget API.

Reverse-engineered from the widget loader at cdn2.chronogolf.com/widgets/v2,
which resolves a club's booking page to https://www.chronogolf.com/club/{slug}
- a Next.js page whose embedded __NEXT_DATA__ carries the real course_id and
affiliation_type_id needed for the actual search call:

    GET https://www.chronogolf.com/marketplace/clubs/{club_id}/teetimes
        ?date={YYYY-MM-DD}&course_id={course_id}&nb_holes={9|18}
        &start_time=00:00&end_time=23:59
        &affiliation_type_ids[]={affiliation_type_id}

"affiliation_type_ids[]" (the public/default rate category) is required -
without it the API 422s with "Player type provided is not valid". No auth.

The response lists only currently-bookable slots and doesn't expose a spots-
remaining count, so (like teesnap_client.py) this assumes a standard foursome
whenever a slot appears at all. holes isn't in the response either - it's
implied by which nb_holes query returned the slot, so both are fetched and
combined per course, same pattern as easytee_client.py.
"""
import concurrent.futures
from datetime import datetime

import requests

REQUEST_TIMEOUT_SECONDS = 10
API_BASE = "https://www.chronogolf.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Not present in the response - a standard golf foursome, matching the group
# sizes actually observed in real booking data (same reasoning as Teesnap).
MAX_PLAYERS_PER_SLOT = 4


def _normalize_entry(course, entry, holes):
    date_str = entry.get("date")
    time_str = entry.get("start_time")
    try:
        parsed = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        hour_12 = parsed.hour % 12 or 12
        display_time = f"{hour_12}:{parsed.minute:02d} {'AM' if parsed.hour < 12 else 'PM'}"
        sort_key = parsed.isoformat()
    except (TypeError, ValueError):
        display_time = time_str
        sort_key = f"{date_str}T00:00:00"

    green_fees = entry.get("green_fees") or []
    price = green_fees[0].get("price") if green_fees else None

    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": f"{date_str} {time_str}",
        "display_time": display_time,
        "sort_key": sort_key,
        "holes": holes,
        "available_spots": MAX_PLAYERS_PER_SLOT,
        "max_players": MAX_PLAYERS_PER_SLOT,
        "price_18": price if holes == 18 else None,
        "price_9": price if holes == 9 else None,
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": course.get("booking_url"),
    }


def _fetch_holes_variant(course, date_str, holes):
    resp = requests.get(
        f"{API_BASE}/marketplace/clubs/{course['club_id']}/teetimes",
        params={
            "date": date_str,
            "course_id": course["course_id"],
            "nb_holes": holes,
            "start_time": "00:00",
            "end_time": "23:59",
            "affiliation_type_ids[]": course["affiliation_type_id"],
        },
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    entries = resp.json()
    if not isinstance(entries, list):
        raise ValueError(f"Unexpected response shape: {type(entries)}")
    return [_normalize_entry(course, e, holes) for e in entries]


def fetch_course_tee_times(course, date_str):
    """course: dict with id, name, club_id, course_id, affiliation_type_id, booking_url.
    date_str must be YYYY-MM-DD.
    """
    try:
        tee_times = _fetch_holes_variant(course, date_str, 18)
        tee_times += _fetch_holes_variant(course, date_str, 9)
    except Exception as exc:  # noqa: BLE001 - surface any failure per-course
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": str(exc),
            "tee_times": [],
        }

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
