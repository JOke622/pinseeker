"""
Client for EasyTee Golf's booking widget (app.easyteegolf.com).

Unlike the other clients, there's no JSON API here - the course page is fully
server-rendered HTML (Django-style templates), so this parses the rendered
listing directly. Still just a plain public GET per request, no auth, no
headless browser/Selenium involved:

    GET {BASE_URL}/course/{slug}/?days={N}         -> 18-hole listing
    GET {BASE_URL}/course/{slug}/?days={N}&p=yes    -> 9-hole listing

"days" is an integer offset from "today" as the server sees it (0 = today);
the two hole counts are separate server-rendered views, so both are fetched
and combined into one list per course.
"""
import concurrent.futures
from datetime import datetime

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT_SECONDS = 10
BASE_URL = "https://app.easyteegolf.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _parse_golfers(text):
    """'1 golfer' -> 1, '1 - 2 golfers' -> 2 (upper bound = spots bookable together)."""
    digits = [int(n) for n in text.split() if n.isdigit()]
    return max(digits) if digits else 0


def _normalize_item(course, item, holes, date_str):
    h3s = item.select("h3")
    time_text = h3s[0].get_text(strip=True) if h3s else ""
    price_text = h3s[1].get_text(strip=True) if len(h3s) > 1 else ""

    price = None
    if price_text.startswith("$"):
        try:
            price = float(price_text[1:].replace(",", ""))
        except ValueError:
            price = None

    muted = item.select_one("h6.text-muted")
    spots = _parse_golfers(muted.get_text(strip=True)) if muted else 0

    try:
        parsed = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %I:%M %p")
        sort_key = parsed.isoformat()
    except ValueError:
        sort_key = f"{date_str}T00:00:00"

    return {
        "course_id": course["id"],
        "course_name": course["name"],
        "datetime": f"{date_str} {time_text}",
        "display_time": time_text,
        "sort_key": sort_key,
        "holes": holes,
        "available_spots": spots,
        "max_players": spots,
        "price_18": price if holes == 18 else None,
        "price_9": price if holes == 9 else None,
        "cart_fee_18": None,
        "cart_fee_9": None,
        "requires_credit_card": False,
        "booking_url": course.get("booking_url"),
    }


def _fetch_holes_variant(course, days_offset, date_str, holes):
    params = {"days": days_offset}
    if holes == 9:
        params["p"] = "yes"
    resp = requests.get(
        f"{BASE_URL}/course/{course['slug']}/",
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(".list-group-item")
    return [_normalize_item(course, item, holes, date_str) for item in items]


def fetch_course_tee_times(course, target_date):
    """course: dict with id, name, slug, booking_url. target_date: a date object."""
    days_offset = (target_date - datetime.now().date()).days
    date_str = target_date.isoformat()

    if days_offset < 0:
        return {
            "course_id": course["id"],
            "course_name": course["name"],
            "error": None,
            "tee_times": [],
        }

    try:
        tee_times = _fetch_holes_variant(course, days_offset, date_str, 18)
        tee_times += _fetch_holes_variant(course, days_offset, date_str, 9)
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


def fetch_all_tee_times(courses, target_date):
    if not courses:
        return []
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(courses)) as pool:
        futures = [pool.submit(fetch_course_tee_times, c, target_date) for c in courses]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results
