import os
import sqlite3
import math
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "wathere.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("WATHERE_SECRET", "change-this-development-secret")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                facility_type TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                operational_status TEXT NOT NULL DEFAULT 'Unknown',
                cleanliness_score INTEGER NOT NULL DEFAULT 50,
                water_quality TEXT NOT NULL DEFAULT 'Not tested',
                last_verified TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_id INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                description TEXT NOT NULL,
                image_filename TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(facility_id) REFERENCES facilities(id)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
        if count == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            sample = [
                ("Community Water Point", "Water", "Sample area - replace with real address", 29.58, 80.22, "Operational", 82, "Not tested", now, "Sample data only"),
                ("Public Toilet - Main Market", "Toilet", "Sample market area - replace with real address", 29.59, 80.21, "Operational", 68, "Not applicable", now, "Sample data only"),
                ("Water Tap - Bus Stand", "Water", "Sample bus stand area - replace with real address", 29.57, 80.23, "Unknown", 50, "Not tested", now, "Sample data only"),
                ("Public Toilet - Park", "Toilet", "Sample park area - replace with real address", 29.60, 80.24, "Non-operational", 35, "Not applicable", now, "Sample data only"),
            ]
            conn.executemany("""
                INSERT INTO facilities
                (name, facility_type, address, latitude, longitude, operational_status,
                 cleanliness_score, water_quality, last_verified, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sample)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def distance_km(lat1, lon1, lat2, lon2):
    radius = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def freshness_label(last_verified):
    try:
        dt = datetime.strptime(last_verified, "%Y-%m-%d %H:%M")
        age = datetime.now() - dt
        if age <= timedelta(hours=24):
            return "Recent"
        if age <= timedelta(days=7):
            return "A few days old"
        return "Outdated"
    except ValueError:
        return "Unknown"

def confidence_score(facility, report_count):
    # Demonstration heuristic, not a scientifically validated score.
    freshness = freshness_label(facility["last_verified"])
    score = 45
    if freshness == "Recent":
        score += 30
    elif freshness == "A few days old":
        score += 15
    score += min(report_count * 5, 15)
    if facility["operational_status"] != "Unknown":
        score += 10
    return min(score, 100)

@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    facility_type = request.args.get("type", "All")
    with connect_db() as conn:
        query = "SELECT * FROM facilities WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR address LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if facility_type in ("Water", "Toilet"):
            query += " AND facility_type = ?"
            params.append(facility_type)
        query += " ORDER BY name"
        facilities = conn.execute(query, params).fetchall()
        reports = conn.execute("""
            SELECT facility_id, COUNT(*) AS total
            FROM reports GROUP BY facility_id
        """).fetchall()
    report_counts = {r["facility_id"]: r["total"] for r in reports}
    cards = []
    for f in facilities:
        item = dict(f)
        item["report_count"] = report_counts.get(f["id"], 0)
        item["freshness"] = freshness_label(f["last_verified"])
        item["confidence"] = confidence_score(f, item["report_count"])
        cards.append(item)
    return render_template("index.html", facilities=cards, q=search, selected_type=facility_type)

@app.route("/facility/<int:facility_id>")
def facility_detail(facility_id):
    with connect_db() as conn:
        facility = conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone()
        reports = conn.execute(
            "SELECT * FROM reports WHERE facility_id = ? ORDER BY id DESC", (facility_id,)
        ).fetchall()
    if not facility:
        flash("Facility not found.", "error")
        return redirect(url_for("index"))
    report_count = len(reports)
    item = dict(facility)
    item["freshness"] = freshness_label(item["last_verified"])
    item["confidence"] = confidence_score(item, report_count)
    return render_template("facility.html", facility=item, reports=reports)

@app.route("/report/<int:facility_id>", methods=["GET", "POST"])
def report_issue(facility_id):
    with connect_db() as conn:
        facility = conn.execute("SELECT * FROM facilities WHERE id = ?", (facility_id,)).fetchone()
    if not facility:
        flash("Facility not found.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        issue_type = request.form.get("issue_type", "").strip()
        description = request.form.get("description", "").strip()
        if not issue_type or not description:
            flash("Please select an issue and enter a description.", "error")
            return redirect(url_for("report_issue", facility_id=facility_id))
        image_filename = None
        image = request.files.get("image")
        if image and image.filename:
            if not allowed_file(image.filename):
                flash("Image must be PNG, JPG, JPEG, or WEBP.", "error")
                return redirect(url_for("report_issue", facility_id=facility_id))
            image_filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}")
            image.save(os.path.join(UPLOAD_DIR, image_filename))
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with connect_db() as conn:
            conn.execute("""
                INSERT INTO reports (facility_id, issue_type, description, image_filename, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (facility_id, issue_type, description, image_filename, now))
            # New reports mark status as needing review; no automatic claim is made.
            conn.execute("UPDATE facilities SET notes = ? WHERE id = ?",
                         ("New community report received; verify before relying on status.", facility_id))
        flash("Report submitted. It is awaiting verification.", "success")
        return redirect(url_for("facility_detail", facility_id=facility_id))
    return render_template("report.html", facility=facility)

@app.route("/admin/add", methods=["GET", "POST"])
def add_facility():
    if request.method == "POST":
        fields = [
            request.form.get("name", "").strip(),
            request.form.get("facility_type", "").strip(),
            request.form.get("address", "").strip(),
            request.form.get("latitude", "").strip(),
            request.form.get("longitude", "").strip(),
            request.form.get("operational_status", "Unknown").strip(),
            request.form.get("cleanliness_score", "50").strip(),
            request.form.get("water_quality", "Not tested").strip(),
            request.form.get("notes", "").strip(),
        ]
        try:
            lat, lon = float(fields[3]), float(fields[4])
            score = max(0, min(100, int(fields[6])))
            if not fields[0] or fields[1] not in ("Water", "Toilet") or not fields[2]:
                raise ValueError
        except ValueError:
            flash("Please enter valid facility details, coordinates, type, and score.", "error")
            return redirect(url_for("add_facility"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with connect_db() as conn:
            conn.execute("""
                INSERT INTO facilities
                (name, facility_type, address, latitude, longitude, operational_status,
                 cleanliness_score, water_quality, last_verified, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (fields[0], fields[1], fields[2], lat, lon, fields[5], score, fields[7], now, fields[8]))
        flash("Facility added.", "success")
        return redirect(url_for("index"))
    return render_template("add_facility.html")

@app.route("/api/nearby")
def nearby_api():
    try:
        lat = float(request.args["lat"])
        lon = float(request.args["lon"])
        radius = float(request.args.get("radius", "5"))
    except (KeyError, ValueError):
        return {"error": "Provide numeric lat and lon parameters."}, 400
    with connect_db() as conn:
        facilities = conn.execute("SELECT * FROM facilities").fetchall()
    results = []
    for f in facilities:
        d = distance_km(lat, lon, f["latitude"], f["longitude"])
        if d <= radius:
            item = dict(f)
            item["distance_km"] = round(d, 2)
            results.append(item)
    results.sort(key=lambda x: x["distance_km"])
    return {"results": results, "count": len(results)}

@app.errorhandler(413)
def too_large(_error):
    flash("Image too large. Maximum upload size is 5 MB.", "error")
    return redirect(url_for("index"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)
