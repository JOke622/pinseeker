"""
Client for Club Prophet Systems' (cps.golf) online reservation API.

Reverse-engineered from the Angular SPA served at https://{site}.cps.golf/onlineresweb/:
1. POST {base}/identityapi/myconnect/token/short  (form field client_id=onlinereswebshortlived)
   -> anonymous short-lived bearer token, no credentials required.
2. POST {base}/onlineres/onlineapi/api/v1/onlinereservation/RegisterTransactionId
   with a client-generated UUID as the transactionId, to "reserve" a search session.
3. GET  {base}/onlineres/onlineapi/api/v1/onlinereservation/TeeTimes
   with that transactionId + search params -> tee time list.

x-websiteid/x-siteid headers are accepted as placeholders (the all-zero GUID and "1"
work even when they don't match the real values) - only courseIds and the date format
actually matter. Each cps.golf "site" can host more than one physical course under
different courseIds (e.g. georgewright.cps.golf serves both William J. Devine and
George Wright under courseId 1 and 2).
"""
import concurrent.futures
import uuid
from datetime import datetime

import requests

REQUEST_TIMEOUT_SECONDS = 10
SHORT_LIVED_CLIENT_ID = "onlinereswebshortlived"
PLACEHOLDER_WEBSITE_ID = "00000000-0000-0000-0000-000000000000"
HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _get_token(base_url):
    resp = requests.post(
        f"{base_url}/identityapi/myconnect/token/short",
        data={"client_id": SHORT_LIVED_CLIENT_ID},
        headers=HEADERS_BASE,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _auth_headers(token, course):
    return {
        **HEADERS_BASE,
        "Authorization": f"Bearer {token}",
        "x-componentid": "1",
        "x-productid": "1",
        "x-websiteid": course.get("website_id", PLACEHOLDER_WEBSITE_ID),
        "x-siteid": str(course.get("site_id", 1)),
    }


def _register_transaction(base_url, headers):
    tx_id = str(uuid.uuid4())
    resp = requests.post(
        f"{base_url}/onlineres/onlineapi/api/v1/onlinereservation/RegisterTransactionId",
        headers={**headers, "Content-Type": "application/json"},
        json={"transactionId": tx_id},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return tx_id


def _price_for(item_prices, hole_count):
    needle = str(hole_count)
    for item in item_prices:
        code = (item.get("shItemCode") or "").lower()
        if "greenfee" in code and needle in code:
            return item.get("displayPrice") or item.get("currentPrice")
    return None


def _normalize_entry(course, entry):
    start = entry.get("startTime")
    try:
        parsed = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
        hour_12 = parsed.hour % 12 or 12
        display_time = f"{hour_12}:{parsed.minute:02d} {'AM' if parsed.hour < 12 else 'PM'}"
        sort_key = parsed.isoformat()
    except (TypeError, ValueError):
        display_time = start
        sort_key = start or ""

    item_prices = entry.get("shItemPrices") or []
    participants = entry.get("participants") or 0
    booked = len(entry.get("bookingList") or [])

    return {
        "course_id": course["id"],
        "course_name": entry.get("courseName") or course["name"],
        "datetime": start,
        "display_time": display_time,
        "sort_key": sort_key,
        "holes": entry.get("holes"),
        "available_spots": max(participants - booked, 0),
        "max_players": participants,
        "price_18": _price_for(item_prices, 18),
        "price_9": _price_for(item_prices, 9),
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": course.get("booking_url"),
    }


def fetch_course_tee_times(course, date_str):
    """course: dict with id, name, cps_site (subdomain), course_id (numeric), booking_url.
    date_str must look like 'Mon Aug 10 2026' (JS Date.toDateString() format: '%a %b %d %Y').
    """
    base_url = f"https://{course['cps_site']}.cps.golf"
    try:
        token = _get_token(base_url)
        headers = _auth_headers(token, course)
        tx_id = _register_transaction(base_url, headers)

        params = {
            "searchDate": date_str,
            "holes": 0,
            "numberOfPlayer": 0,
            "courseIds": course["course_id"],
            "searchTimeType": 0,
            "transactionId": tx_id,
            "teeOffTimeMin": 0,
            "teeOffTimeMax": 23,
            "isChangeTeeOffTime": "true",
            "teeSheetSearchView": 5,
            "classCode": "R",
            "defaultOnlineRate": "N",
            "isUseCapacityPricing": "false",
            "memberStoreId": 1,
            "searchType": 1,
        }
        resp = requests.get(
            f"{base_url}/onlineres/onlineapi/api/v1/onlinereservation/TeeTimes",
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("isSuccess", True):
            raise ValueError(f"API reported failure: {payload}")
        content = payload.get("content")
        entries = content if isinstance(content, list) else []
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
