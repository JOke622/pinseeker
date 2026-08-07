import truststore

truststore.inject_into_ssl()  # trust the OS (corporate) certificate store, needed on this network

import concurrent.futures
from datetime import datetime

from flask import Flask, jsonify, render_template, request

import clubprophet_client
import easytee_client
import foreup_client
import teeitup_client
from courses import CLUBPROPHET_COURSES, EASYTEE_COURSES, FOREUP_COURSES, TEEITUP_COURSES

app = Flask(__name__)

ALL_COURSES = FOREUP_COURSES + CLUBPROPHET_COURSES + TEEITUP_COURSES + EASYTEE_COURSES
REGIONS = sorted({c["region"] for c in ALL_COURSES})


@app.route("/")
def index():
    return render_template("index.html", courses=ALL_COURSES, regions=REGIONS)


@app.route("/api/tee-times")
def api_tee_times():
    date_param = request.args.get("date")  # expected YYYY-MM-DD from <input type=date>
    holes = request.args.get("holes", "all")
    try:
        players = int(request.args.get("players", 0))
    except ValueError:
        return jsonify({"error": "players must be an integer"}), 400

    if date_param:
        try:
            parsed_date = datetime.strptime(date_param, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    else:
        parsed_date = datetime.now()

    foreup_date_str = parsed_date.strftime("%m-%d-%Y")
    clubprophet_date_str = parsed_date.strftime("%a %b %d %Y")
    teeitup_date_str = parsed_date.strftime("%Y-%m-%d")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        foreup_future = pool.submit(
            foreup_client.fetch_all_tee_times, FOREUP_COURSES, foreup_date_str, holes, players
        )
        clubprophet_future = pool.submit(
            clubprophet_client.fetch_all_tee_times, CLUBPROPHET_COURSES, clubprophet_date_str
        )
        teeitup_future = pool.submit(
            teeitup_client.fetch_all_tee_times, TEEITUP_COURSES, teeitup_date_str
        )
        easytee_future = pool.submit(
            easytee_client.fetch_all_tee_times, EASYTEE_COURSES, parsed_date.date()
        )
        results = (
            foreup_future.result()
            + clubprophet_future.result()
            + teeitup_future.result()
            + easytee_future.result()
        )

    # Only ForeUp's API actually honors the holes/players params server-side (and
    # the other platforms ignore them entirely), so re-filter everything here to
    # keep behavior consistent. Some ForeUp schedules (e.g. Pease) report a
    # flexible hole count like "9/18" instead of a single number - treat that
    # as matching either.
    if holes != "all":
        for r in results:
            r["tee_times"] = [
                tt for tt in r["tee_times"] if holes in str(tt.get("holes")).split("/")
            ]

    if players > 0:
        for r in results:
            r["tee_times"] = [
                tt for tt in r["tee_times"] if (tt.get("available_spots") or 0) >= players
            ]

    combined = [tt for r in results for tt in r["tee_times"]]
    combined.sort(key=lambda tt: tt["sort_key"])

    return jsonify({
        "date": date_param or parsed_date.strftime("%Y-%m-%d"),
        "courses": results,
        "tee_times": combined,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
