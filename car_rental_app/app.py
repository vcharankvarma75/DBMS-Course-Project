"""Car Rental Reservation & Vehicle Return Management System - Flask + SQLite backend."""
import os
import re
import sqlite3
from datetime import date, datetime
from math import ceil

from flask import Flask, g, jsonify, request

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("CARRENTAL_DB", os.path.join(BASE, "carrental.db"))
app = Flask(__name__, static_folder="static", static_url_path="")

# Whitelisted writable columns per table (also protects against SQL injection in table/column names)
TABLES = {
    "branches": ["name", "city", "state"],
    "customers": ["name", "phone", "email", "license_no", "city"],
    "vehicles": ["reg_no", "make_model", "category", "daily_rate", "branch_id", "status"],
    "reservations": ["customer_id", "vehicle_id", "pickup_branch_id", "start_date", "end_date", "status"],
    "rentals": ["reservation_id", "pickup_datetime", "odometer_out", "fuel_out", "deposit"],
    "returns": ["rental_id", "return_datetime", "odometer_in", "damage_notes", "late_fee"],
    "payments": ["rental_id", "amount", "mode", "status"],
}
LATE_FEE_RATE = 0.10  # of daily rate, per late hour


# ---------- database helpers ----------
def init_db():
    if os.path.exists(DB_PATH):
        return
    con = sqlite3.connect(DB_PATH)
    for f in ("schema.sql", "seed.sql"):
        with open(os.path.join(BASE, f), encoding="utf-8") as fh:
            con.executescript(fh.read())
    con.commit()
    con.close()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def log(msg):
    db().execute("INSERT INTO activity_log (message) VALUES (?)", (msg,))


def rows(sql, args=()):
    return [dict(r) for r in db().execute(sql, args).fetchall()]


def friendly(msg):
    m = re.match(r"UNIQUE constraint failed: (\w+)\.(\w+)", msg)
    if m:
        return f"{m.group(2)} must be unique - a record with this value already exists"
    if "FOREIGN KEY" in msg:
        return "Foreign key violation: a linked record is missing, or this record is still used by other tables"
    if "CHECK constraint" in msg:
        return "Value violates a rule (check dates, amounts and allowed options)"
    if "NOT NULL" in msg:
        return "A required field is empty"
    return msg


@app.errorhandler(sqlite3.Error)
def db_error(e):
    try:
        db().rollback()
    except Exception:
        pass
    return jsonify(error=friendly(str(e))), 400


class ApiError(Exception):
    def __init__(self, msg, code=400):
        self.msg, self.code = msg, code


@app.errorhandler(ApiError)
def api_error(e):
    return jsonify(error=e.msg), e.code


def check_table(t):
    if t not in TABLES:
        raise ApiError("Unknown table", 404)


def clean(t, data):
    out = []
    for c in TABLES[t]:
        v = data.get(c)
        out.append(None if v == "" else v)
    return out


# ---------- generic CRUD ----------
@app.get("/api/<t>")
def list_rows(t):
    check_table(t)
    return jsonify(rows(f"SELECT * FROM {t} ORDER BY id"))


@app.post("/api/<t>")
def create_row(t):
    check_table(t)
    cols = TABLES[t]
    cur = db().execute(
        f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        clean(t, request.get_json(force=True)),
    )
    log(f"Added {t[:-1]} #{cur.lastrowid}")
    db().commit()
    return jsonify(id=cur.lastrowid), 201


@app.put("/api/<t>/<int:rid>")
def update_row(t, rid):
    check_table(t)
    cols = TABLES[t]
    cur = db().execute(
        f"UPDATE {t} SET {','.join(c + '=?' for c in cols)} WHERE id=?",
        clean(t, request.get_json(force=True)) + [rid],
    )
    if cur.rowcount == 0:
        raise ApiError("Record not found", 404)
    log(f"Updated {t[:-1]} #{rid}")
    db().commit()
    return jsonify(ok=True)


@app.delete("/api/<t>/<int:rid>")
def delete_row(t, rid):
    check_table(t)
    cur = db().execute(f"DELETE FROM {t} WHERE id=?", (rid,))
    if cur.rowcount == 0:
        raise ApiError("Record not found", 404)
    log(f"Deleted {t[:-1]} #{rid}")
    db().commit()
    return jsonify(ok=True)


# ---------- business operations (each runs as ONE transaction) ----------
@app.post("/api/reservations/<int:rid>/pickup")
def pickup(rid):
    d = request.get_json(force=True)
    cur = db().execute(
        "INSERT INTO rentals (reservation_id, pickup_datetime, odometer_out, fuel_out, deposit) VALUES (?,?,?,?,?)",
        (rid, d.get("pickup_datetime") or datetime.now().strftime("%Y-%m-%dT%H:%M"),
         d.get("odometer_out") or 0, d.get("fuel_out") or "Full", d.get("deposit") or 0),
    )
    log(f"Pickup: rental #{cur.lastrowid} created for reservation #{rid}; vehicle marked Rented")
    db().commit()
    return jsonify(id=cur.lastrowid), 201


@app.post("/api/rentals/<int:rid>/return")
def vehicle_return(rid):
    d = request.get_json(force=True)
    r = db().execute(
        """SELECT rt.pickup_datetime, rt.odometer_out, rs.start_date, rs.end_date, v.daily_rate, v.reg_no
           FROM rentals rt JOIN reservations rs ON rs.id = rt.reservation_id
           JOIN vehicles v ON v.id = rs.vehicle_id WHERE rt.id = ?""", (rid,)).fetchone()
    if not r:
        raise ApiError("Rental not found", 404)
    try:
        returned = datetime.fromisoformat(d["return_datetime"])
        odo_in = int(d["odometer_in"])
    except (KeyError, ValueError):
        raise ApiError("Return time and odometer are required")
    if odo_in < r["odometer_out"]:
        raise ApiError("Odometer in cannot be less than odometer out")
    due = datetime.fromisoformat(r["end_date"] + "T" + r["pickup_datetime"][11:16])
    late_hours = max(0, ceil((returned - due).total_seconds() / 3600))
    late_fee = round(late_hours * r["daily_rate"] * LATE_FEE_RATE)
    days = max(1, (date.fromisoformat(r["end_date"]) - date.fromisoformat(r["start_date"])).days)
    bill = days * r["daily_rate"] + late_fee
    # return + payment inserted in the same transaction (triggers free the vehicle)
    cur = db().execute(
        "INSERT INTO returns (rental_id, return_datetime, odometer_in, damage_notes, late_fee) VALUES (?,?,?,?,?)",
        (rid, d["return_datetime"], odo_in, d.get("damage_notes") or "None", late_fee))
    db().execute("INSERT INTO payments (rental_id, amount, mode, status) VALUES (?,?,'UPI','Pending')", (rid, bill))
    log(f"Return: {r['reg_no']} back and Available; bill Rs {bill:,.0f} (late {late_hours}h, fee Rs {late_fee})")
    db().commit()
    return jsonify(id=cur.lastrowid, late_hours=late_hours, late_fee=late_fee, bill=bill), 201


# ---------- reports ----------
@app.get("/api/dashboard")
def dashboard():
    one = lambda sql: db().execute(sql).fetchone()[0]
    return jsonify(
        customers=one("SELECT COUNT(*) FROM customers"),
        vehicles=one("SELECT COUNT(*) FROM vehicles"),
        available=one("SELECT COUNT(*) FROM vehicles WHERE status='Available'"),
        rented=one("SELECT COUNT(*) FROM vehicles WHERE status='Rented'"),
        open_reservations=one("SELECT COUNT(*) FROM reservations WHERE status IN ('Pending','Confirmed')"),
        active_rentals=one("SELECT COUNT(*) FROM rentals WHERE id NOT IN (SELECT rental_id FROM returns)"),
        revenue=one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='SUCCESS'"),
        pending=one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='Pending'"),
        fleet=rows("""SELECT b.name, COUNT(v.id) AS vehicles,
                      SUM(v.status='Available') AS available, SUM(v.status='Rented') AS rented
                      FROM branches b LEFT JOIN vehicles v ON v.branch_id = b.id GROUP BY b.id"""),
        revenue_by_branch=rows("SELECT * FROM v_revenue_by_branch"),
        activity=rows("SELECT ts, message FROM activity_log ORDER BY id DESC LIMIT 8"),
    )


@app.get("/api/available")
def available():
    start, end, branch = request.args.get("start"), request.args.get("end"), request.args.get("branch_id")
    if not start or not end:
        raise ApiError("start and end dates are required")
    sql = """SELECT v.id, v.reg_no, v.make_model, v.category, v.daily_rate FROM vehicles v
             WHERE v.status = 'Available' AND (? = '' OR v.branch_id = ?)
             AND v.id NOT IN (SELECT vehicle_id FROM reservations WHERE status NOT IN ('Cancelled','Completed')
                              AND start_date <= ? AND end_date >= ?)"""
    return jsonify(rows(sql, (branch or "", branch or "", end, start)))


@app.post("/api/sql")
def sql_console():
    """Read-only SQL console for demonstrating queries (SELECT / WITH only)."""
    sql = (request.get_json(force=True).get("sql") or "").strip().rstrip(";")
    if not re.match(r"(?is)^(select|with)\b", sql):
        raise ApiError("Only SELECT queries are allowed in the console")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql)
        data = cur.fetchmany(200)
        cols = [c[0] for c in cur.description]
        return jsonify(columns=cols, rows=[list(r) for r in data])
    except sqlite3.Error as e:
        raise ApiError(str(e))
    finally:
        con.close()


@app.get("/")
def index():
    return app.send_static_file("index.html")


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
