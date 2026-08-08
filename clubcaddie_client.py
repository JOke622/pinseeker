"""
Client for ClubCaddie's booking widget (apimanager-{tenant}.clubcaddie.com).

Reverse-engineered from the widget embedded via iframe on the course's own site:
1. GET  {base_url}/webapi/view/{apikey}?SetSessionIdInLocalStorage=true
   -> a `Session-Id` response header (no credentials, just a session token)
2. GET  {base_url}/webapi/view/{apikey}/slots?date=..&player=1&ratetype=any&Interaction={session_id}
   -> establishes that session server-side via cookies. Required - step 3 silently
      returns an empty body without it (this mirrors what a real browser does
      automatically via inline JS + localStorage on first visit).
3. POST {base_url}/webapi/TeeTimes  (form-encoded, same session/cookies)
   -> an HTML fragment, not JSON, but each tee time's full data is embedded as a
      URL+JSON-encoded `<input name="slot" value="...">` hidden field.

"apikey" is the tenant slug (e.g. "gafdabab" for Trull Brook). "course_id" is a
numeric id specific to the physical course, found in the rendered search form
(a tenant could in principle host more than one course under the same apikey).
"""
import concurrent.futures
import json
import re
from datetime import datetime
from urllib.parse import unquote

import requests

REQUEST_TIMEOUT_SECONDS = 10
HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
SLOT_RE = re.compile(r'name="slot" value="([^"]+)"')


def _establish_session(base_url, apikey, date_str):
    session = requests.Session()
    session.headers.update(HEADERS_BASE)
    resp = session.get(
        f"{base_url}/webapi/view/{apikey}",
        params={"SetSessionIdInLocalStorage": "true"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    session_id = resp.headers.get("Session-Id")
    session.get(
        f"{base_url}/webapi/view/{apikey}/slots",
        params={"date": date_str, "player": 1, "ratetype": "any", "Interaction": session_id},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return session


def _price_for(pricing_plan, key):
    prices = [p[key] for p in pricing_plan if p.get(key) is not None]
    return min(prices) if prices else None


def _normalize_slot(course, slot, date_str):
    price_9 = _price_for(slot.get("PricingPlan") or [], "HoleRate_9")
    price_18 = _price_for(slot.get("PricingPlan") or [], "HoleRate_18")
    holes = "/".join(h for h, p in (("9", price_9), ("18", price_18)) if p is not None) or None

    try:
        parsed = datetime.strptime(f"{date_str} {slot['StartTime']}", "%m/%d/%Y %H:%M:%S")
        hour_12 = parsed.hour % 12 or 12
        display_time = f"{hour_12}:{parsed.minute:02d} {'AM' if parsed.hour < 12 else 'PM'}"
        sort_key = parsed.isoformat()
    except (KeyError, ValueError):
        display_time = slot.get("StartTime", "")
        sort_key = ""

    spots = slot.get("PlayersAvailable") or 0
    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": f"{date_str} {slot.get('StartTime', '')}",
        "display_time": display_time,
        "sort_key": sort_key,
        "holes": holes,
        "available_spots": spots,
        "max_players": spots,
        "price_18": price_18,
        "price_9": price_9,
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": f"{course['booking_url']}/slots?date={date_str}&player=1&ratetype=any",
    }


def fetch_course_tee_times(course, date_str):
    """course: dict with id, name, base_url, apikey, course_id, booking_url.
    date_str must be MM/DD/YYYY.
    """
    try:
        session = _establish_session(course["base_url"], course["apikey"], date_str)
        data = {
            "date": date_str,
            "player": 1,
            "holes": "any",
            "fromtime": 0,
            "totime": 24,
            "minprice": 0,
            "maxprice": 99999,
            "HoleGroup": "all",
            "CourseId": course["course_id"],
            "apikey": course["apikey"],
        }
        resp = session.post(
            f"{course['base_url']}/webapi/TeeTimes",
            data=data,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        slots = [json.loads(unquote(s)) for s in SLOT_RE.findall(resp.text)]
    except Exception as exc:  # noqa: BLE001 - surface any failure per-course
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": str(exc),
            "tee_times": [],
        }

    tee_times = [_normalize_slot(course, s, date_str) for s in slots]
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
