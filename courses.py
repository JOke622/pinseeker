"""
Configured golf courses to search, grouped by booking platform.
Sourced from the user's "Tee Time bookings" bookmarks folder (2026-08-07).

--- ForeUp ---
To add a course: find its booking page, e.g.
    https://foreupsoftware.com/index.php/booking/{course_id}/{schedule_id}#/teetimes
and copy the {schedule_id} (the second number in the URL) below.

--- Club Prophet (cps.golf) ---
To add a course: find its booking page, e.g. https://{site}.cps.golf/onlineresweb/...
"cps_site" is that subdomain. "course_id" is NOT in the URL - it has to be found by
trial (1, 2, 3...) against the TeeTimes API, since one cps.golf site can host more
than one physical course (e.g. georgewright.cps.golf serves both William J. Devine
and George Wright under different course_ids).
"""

FOREUP_COURSES = [
    {
        "id": "ledges",
        "name": "The Ledges Golf Club",
        "region": "Southern Maine/New Hampshire",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "12190",
        "booking_url": "https://foreupsoftware.com/index.php/booking/22874/12190#/teetimes",
    },
    {
        "id": "hickory_hill",
        "name": "Hickory Hill Golf Course",
        "region": "North Shore",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "1829",
        "booking_url": "https://foreupsoftware.com/index.php/booking/19557/1829#/teetimes",
    },
    {
        "id": "far_corner",
        "name": "Far Corner Golf Club",
        "region": "North Shore",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "11259",
        "booking_url": "https://foreupsoftware.com/index.php/booking/22586/11259#/teetimes",
    },
    {
        "id": "brookline",
        "name": "Robert T. Lynch Municipal (Brookline Golf Course)",
        "region": "Greater Boston",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "2748",
        "booking_url": "https://foreupsoftware.com/index.php/booking/19865/2748#/teetimes",
    },
    {
        "id": "newton_commonwealth",
        "name": "Newton Commonwealth Golf Course",
        "region": "Greater Boston",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "6440",
        "booking_url": "https://foreupsoftware.com/index.php/booking/21009/6440#/teetimes",
    },
    {
        "id": "stow_acres",
        "name": "Stow Acres Country Club",
        "region": "Metro West",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "3228",
        "booking_url": "https://foreupsoftware.com/index.php/booking/19972/3228#/teetimes",
    },
    {
        "id": "pease",
        "name": "Pease Golf Course",
        "region": "Southern Maine/New Hampshire",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "12886",
        "booking_url": "https://foreupsoftware.com/index.php/booking/22471/12886#/teetimes",
    },
    {
        "id": "wayland",
        "name": "Wayland Country Club",
        "region": "Metro West",
        "base_url": "https://foreupsoftware.com",
        "schedule_id": "6536",
        "booking_url": "https://foreupsoftware.com/index.php/booking/21030/6536#/teetimes",
    },
]

CLUBPROPHET_COURSES = [
    {
        "id": "butter_brook",
        "name": "Butter Brook Golf Club",
        "region": "Metro West",
        "cps_site": "butterbrook",
        "course_id": 1,
        "booking_url": "https://butterbrook.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "shaker_hills",
        "name": "Shaker Hills Country Club",
        "region": "Metro West",
        "cps_site": "shakerhillscc",
        "course_id": 1,
        # this tenant validates x-websiteid/x-siteid against its real values,
        # unlike the others which accept a placeholder - see clubprophet_client.py
        "website_id": "6d6b8b35-71f1-4860-0c03-08da075443d6",
        "site_id": 1,
        "booking_url": "https://shakerhillscc.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "red_tail",
        "name": "Red Tail Golf Club",
        "region": "Metro West",
        "cps_site": "redtailgc",
        "course_id": 2,
        "booking_url": "https://redtailgc.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "gannon",
        "name": "Gannon Municipal Golf Course",
        "region": "Greater Boston",
        "cps_site": "gannon",
        "course_id": 1,
        "booking_url": "https://gannon.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "atlantic_pines",
        "name": "Atlantic Pines Golf Club",
        "region": "Southern Maine/New Hampshire",
        "cps_site": "atlanticpines",
        "course_id": 2,
        "booking_url": "https://atlanticpines.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "links_at_outlook",
        "name": "The Links at Outlook",
        "region": "Southern Maine/New Hampshire",
        "cps_site": "atlanticpines",
        "course_id": 1,
        "booking_url": "https://atlanticpines.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "william_j_devine",
        "name": "William J. Devine Golf Course",
        "region": "Greater Boston",
        "cps_site": "georgewright",
        "course_id": 1,
        "booking_url": "https://georgewright.cps.golf/onlineresweb/search-teetime",
    },
    {
        "id": "george_wright",
        "name": "George Wright Golf Course",
        "region": "Greater Boston",
        "cps_site": "georgewright",
        "course_id": 2,
        "booking_url": "https://georgewright.cps.golf/onlineresweb/search-teetime",
    },
]

# --- TeeItUp / Lightspeed Golf (book.teeitup.com / play.teeitup.com) ---
# "alias" is the site's subdomain (before .book/.play.teeitup.com/.golf) - it alone
# scopes API results to the right facility, so "facility_id" is optional (only
# butternut_farm/campbells_scottish_highlands have it, carried over from when
# they were first added; harmless either way).
TEEITUP_COURSES = [
    {
        "id": "butternut_farm",
        "name": "Butternut Farm Golf Club",
        "region": "Metro West",
        "alias": "butternut-farm-golf-club",
        "facility_id": "17036",
        "booking_url": "https://butternut-farm-golf-club.book.teeitup.com/?course=17036",
    },
    {
        "id": "campbells_scottish_highlands",
        "name": "Campbell's Scottish Highlands",
        "region": "Southern Maine/New Hampshire",
        "alias": "6391c422-2e57-4bc3-a1b3-8a6676c82588",
        "facility_id": "15773",
        "booking_url": "https://6391c422-2e57-4bc3-a1b3-8a6676c82588.book.teeitup.com/?course=15773",
    },
    {
        "id": "breakfast_hill",
        "name": "Breakfast Hill Golf Club",
        "region": "Southern Maine/New Hampshire",
        "alias": "breakfast-hill-golf-club",
        "booking_url": "https://breakfast-hill-golf-club.book.teeitup.golf",
    },
    {
        "id": "olde_scotland_links",
        "name": "Olde Scotland Links",
        "region": "South Shore",
        "alias": "7c60cf72-5f0a-45cc-bfcb-2075f12c45ab",
        "booking_url": "https://7c60cf72-5f0a-45cc-bfcb-2075f12c45ab.book.teeitup.com/",
    },
    {
        "id": "braintree_municipal",
        "name": "Braintree Municipal Golf Course",
        "region": "South Shore",
        "alias": "braintree-municipal-golf-course",
        "booking_url": "https://braintree-municipal-golf-course.book.teeitup.com/",
    },
    {
        "id": "crosswinds",
        "name": "Crosswinds Golf Club",
        "region": "South Shore",
        "alias": "c89e81dd-f47b-40ff-a530-6352b36dbdcb",
        "booking_url": "https://c89e81dd-f47b-40ff-a530-6352b36dbdcb.play.teeitup.com",
    },
]

# --- EasyTee Golf (app.easyteegolf.com) ---
# No JSON API - server-rendered HTML pages, parsed directly by easytee_client.py.
# "slug" is the {slug} in https://app.easyteegolf.com/course/{slug}/.
EASYTEE_COURSES = [
    {
        "id": "granite_fields",
        "name": "Granite Fields Golf Club",
        "region": "Southern Maine/New Hampshire",
        "slug": "granite-fields-golf-club",
        "booking_url": "https://app.easyteegolf.com/course/granite-fields-golf-club/",
    },
]

# --- ClubCaddie (apimanager-{tenant}.clubcaddie.com) ---
# No JSON API - a jQuery-era booking widget, parsed by clubcaddie_client.py.
# "apikey" is the tenant slug from the iframe URL. "course_id" is a numeric id
# specific to the physical course, found in the rendered search form.
CLUBCADDIE_COURSES = [
    {
        "id": "trull_brook",
        "name": "Trull Brook Golf Course & Tennis Center",
        "region": "North Shore",
        "base_url": "https://apimanager-cc29.clubcaddie.com",
        "apikey": "gafdabab",
        "course_id": "103407",
        "booking_url": "https://apimanager-cc29.clubcaddie.com/webapi/view/gafdabab",
    },
]

# --- Teesnap (https://{subdomain}.teesnap.net) ---
# No JSON API in the usual sense - an AngularJS app whose "Teetimes"/"Request"
# services hit a plain GET, parsed by teesnap_client.py. "course_id" comes from
# `window.courses` embedded in the page's initial HTML.
TEESNAP_COURSES = [
    {
        "id": "sandy_burr",
        "name": "Sandy Burr Country Club",
        "region": "Metro West",
        "subdomain": "sandyburr",
        "course_id": 471,
        "booking_url": "https://sandyburr.teesnap.net/",
    },
]
