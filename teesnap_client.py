"""
Client for Teesnap's booking widget (an AngularJS app at https://{subdomain}.teesnap.net/).

Reverse-engineered from the app's compiled JS bundle (the "Request"/"Teetimes"
Angular services): a single public GET, no auth, but requires a Referer header
matching the site itself or the request gets a bare 403.

    GET https://{subdomain}.teesnap.net/customer-api/teetimes-day
        ?course={course_id}&date={YYYY-MM-DD}&players=0&holes=0&addons=0&profileId=

Response shape is unusual: each slot lists which booking IDs occupy it
(teeOffSections[].bookings), and golfer counts live in a separate top-level
"bookings" array keyed by that same ID - so availability has to be computed by
cross-referencing the two, rather than being a single field on the slot.

Note: granitefields.teesnap.net (a different course) returned persistent 500s
when this was first tried - that looks specific to that subdomain, not
Teesnap as a platform, since sandyburr.teesnap.net works fine.
"""
import concurrent.futures

import requests

REQUEST_TIMEOUT_SECONDS = 10
HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Not present anywhere in the API response - a standard golf foursome, matching
# the group sizes actually observed in real booking data.
MAX_PLAYERS_PER_SLOT = 4


def _price_for(prices, round_type):
    for p in prices:
        if p.get("roundType") == round_type:
            try:
                return float(p["price"])
            except (TypeError, ValueError):
                return None
    return None


def _normalize_slot(course, slot, bookings_by_id):
    teetime = slot.get("teeTime") or ""
    try:
        hour, minute = int(teetime[11:13]), int(teetime[14:16])
        hour_12 = hour % 12 or 12
        display_time = f"{hour_12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
        sort_key = teetime
    except (ValueError, IndexError):
        display_time = teetime
        sort_key = teetime

    booked = 0
    held = False
    for section in slot.get("teeOffSections") or []:
        if section.get("isHeld"):
            held = True
        for booking_id in section.get("bookings") or []:
            booking = bookings_by_id.get(booking_id)
            if booking:
                booked += len(booking.get("golfers") or [])
    available = 0 if held else max(MAX_PLAYERS_PER_SLOT - booked, 0)

    prices = slot.get("prices") or []
    price_9 = _price_for(prices, "NINE_HOLE")
    price_18 = _price_for(prices, "EIGHTEEN_HOLE")
    holes = "/".join(h for h, p in (("9", price_9), ("18", price_18)) if p is not None) or None

    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": teetime,
        "display_time": display_time,
        "sort_key": sort_key,
        "holes": holes,
        "available_spots": available,
        "max_players": MAX_PLAYERS_PER_SLOT,
        "price_18": price_18,
        "price_9": price_9,
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": course.get("booking_url"),
    }


def fetch_course_tee_times(course, date_str):
    """course: dict with id, name, subdomain, course_id, booking_url.
    date_str must be YYYY-MM-DD.
    """
    base_url = f"https://{course['subdomain']}.teesnap.net"
    try:
        resp = requests.get(
            f"{base_url}/customer-api/teetimes-day",
            params={
                "course": course["course_id"],
                "date": date_str,
                "players": 0,
                "holes": 0,
                "addons": 0,
                "profileId": "",
            },
            headers={**HEADERS_BASE, "Referer": f"{base_url}/"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code == 400 and resp.json().get("errors") == "date_not_allowed":
            # Requested date is outside this course's booking window - that's
            # not a failure, just "nothing to show yet" like any other date
            # with no availability.
            return {
                "course_id": course["id"],
                "course_name": course["name"],
                "error": None,
                "tee_times": [],
            }
        resp.raise_for_status()
        payload = resp.json().get("teeTimes") or {}
        slots = payload.get("teeTimes") or []
        bookings_by_id = {b["bookingId"]: b for b in payload.get("bookings") or []}
    except Exception as exc:  # noqa: BLE001 - surface any failure per-course
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": str(exc),
            "tee_times": [],
        }

    tee_times = [_normalize_slot(course, s, bookings_by_id) for s in slots]
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
