import os
import time
import json
import sqlite3
import requests
from flask import Flask, jsonify, request, send_from_directory
from functools import lru_cache
from datetime import datetime

app = Flask(__name__, static_folder="static", static_url_path="/static")

REDASH_BASE = "https://dash.prod.bi.auto1.team"
REDASH_KEY = "Cbw7xonVpyBrDWTf09oLhFvCwdTS5EYv32iK7avK"
REDASH_DS = 89
DB_PATH = "recommendations.db"

FUEL_MAP = {
    "Benzin": "Gasolina", "benzin": "Gasolina",
    "Diesel": "Diesel", "diesel": "Diesel",
    "Hybrid": "Híbrido", "hybrid": "Híbrido",
    "Elektro": "Elétrico", "elektro": "Elétrico",
    "LPG": "GPL", "CNG": "GNV", "Mildhybrid": "Mild Hybrid",
}


# ── DB setup ──────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_number TEXT,
            make TEXT,
            model TEXT,
            built_year INTEGER,
            mileage INTEGER,
            auto1_price REAL,
            pvp_ideal REAL,
            service_costs REAL,
            transport REAL,
            obra REAL,
            margin REAL,
            ideal_buy_price REAL,
            difference REAL,
            client_id TEXT,
            client_name TEXT,
            am_name TEXT,
            message TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ── Redash helpers ────────────────────────────────────────────────────────────

def run_redash_query(sql, max_age=3600):
    headers = {"Authorization": f"Key {REDASH_KEY}"}
    r = requests.post(
        f"{REDASH_BASE}/api/query_results",
        headers=headers,
        json={"data_source_id": REDASH_DS, "query": sql, "max_age": max_age},
        timeout=30,
    )
    r.raise_for_status()
    resp = r.json()

    # Redash may return a cached result immediately (no job needed)
    if "query_result" in resp:
        return resp["query_result"]["data"]["rows"]

    # Otherwise a job was queued — poll until done
    if "job" not in resp:
        raise RuntimeError(f"Resposta inesperada do Redash: {list(resp.keys())}")

    job_id = resp["job"]["id"]
    for _ in range(30):
        time.sleep(2)
        jr = requests.get(
            f"{REDASH_BASE}/api/jobs/{job_id}", headers=headers, timeout=15
        ).json()["job"]
        if jr["status"] == 3:
            result_id = jr["result"]
            data = requests.get(
                f"{REDASH_BASE}/api/query_results/{result_id}",
                headers=headers,
                timeout=15,
            ).json()
            return data["query_result"]["data"]["rows"]
        if jr["status"] == 4:
            raise RuntimeError(f"Redash query failed: {jr.get('error')}")

    raise TimeoutError("Redash query timed out after 60s")


# ── Car data ──────────────────────────────────────────────────────────────────

CARS_CACHE = {"data": None, "ts": 0}
CACHE_TTL = 3600  # 1 hour


def normalize_car(row):
    fuel_raw = row.get("fuel_type") or ""
    accident = row.get("car_attr_accident_bool")
    origin = row.get("country_of_registration")
    return {
        "stock_number": row.get("stock_number", ""),
        "make": row.get("make", ""),
        "model": row.get("model", ""),
        "built_year": row.get("built_year"),
        "mileage": row.get("mileage"),
        "fuel_type": FUEL_MAP.get(fuel_raw, fuel_raw),
        "condition": "Não acidentado" if accident == 0 else ("Acidentado" if accident == 1 else "Desconhecido"),
        "origin": "Nacional" if origin == "PT" else ("Importado" if origin else "Desconhecido"),
        "auto1_price": row.get("auto1_price_eur"),
        "branch": row.get("branch_name", ""),
        "url": f"https://www.auto1.com/pt/app/merchant/car/{row.get('stock_number', '')}",
    }


def get_all_cars():
    now = time.time()
    if CARS_CACHE["data"] and (now - CARS_CACHE["ts"]) < CACHE_TTL:
        return CARS_CACHE["data"]

    sql = """
        SELECT
          wl.stock_number,
          wl.make,
          wl.model,
          wl.built_year,
          wl.mileage,
          wl.fuel_type,
          wl.branch_name,
          cd.car_attr_accident_bool,
          cd.country_of_registration,
          ROUND(ccp.amount / 100.0, 0) AS auto1_price_eur
        FROM wkda_dm_es.wkda_leads wl
        LEFT JOIN wkda_dm_es.car_details cd ON cd.id = wl.car_id
        LEFT JOIN wkda_dm_es.car_current_prices ccp
          ON ccp.car_id = wl.car_id AND ccp.type = 'auto1_price'
        WHERE wl.country = 'PT'
          AND wl.lead_status_id = 6
        ORDER BY wl.submitted_at DESC
    """
    rows = run_redash_query(sql, max_age=3600)
    cars = [normalize_car(r) for r in rows]
    CARS_CACHE["data"] = cars
    CARS_CACHE["ts"] = now
    return cars


def get_car_by_stock(stock_number):
    sql = f"""
        SELECT
          wl.stock_number,
          wl.make,
          wl.model,
          wl.built_year,
          wl.mileage,
          wl.fuel_type,
          wl.branch_name,
          wl.dat_ecode,
          cd.car_attr_accident_bool,
          cd.country_of_registration,
          cd.first_registration_date,
          cd.vin,
          cl.car_type_id,
          rct.mtype_detail,
          rct.subtype_annex,
          rct.kw,
          rct.horsepower,
          ROUND(ccp.amount / 100.0, 0) AS auto1_price_eur
        FROM wkda_dm_es.wkda_leads wl
        LEFT JOIN wkda_dm_es.car_details cd ON cd.id = wl.car_id
        LEFT JOIN wkda_dm_es.car_leads cl ON cl.id = wl.car_id
        LEFT JOIN wkda_dm_es.ref_car_types rct ON rct.id = cl.car_type_id
        LEFT JOIN wkda_dm_es.car_current_prices ccp
          ON ccp.car_id = wl.car_id AND ccp.type = 'auto1_price'
        WHERE wl.stock_number = '{stock_number.upper()}'
    """
    rows = run_redash_query(sql, max_age=0)
    if not rows:
        return None
    row = rows[0]

    # Build version string from ref_car_types if available
    version_parts = []
    if row.get("mtype_detail"):
        version_parts.append(row["mtype_detail"].replace(f"{row.get('make','')} {row.get('model','')}", "").strip())
    if row.get("subtype_annex"):
        version_parts.append(row["subtype_annex"])
    version = " ".join(p for p in version_parts if p) or ""

    car = normalize_car(row)
    car["version"] = version
    car["kw"] = row.get("kw")
    car["horsepower"] = row.get("horsepower")
    car["vin"] = row.get("vin")
    car["first_registration_date"] = row.get("first_registration_date")
    return car


# ── Routes: Cars ──────────────────────────────────────────────────────────────

@app.get("/api/cars")
def api_list_cars():
    try:
        cars = get_all_cars()
        # Optional filters
        make = request.args.get("make", "").strip().lower()
        fuel = request.args.get("fuel", "").strip().lower()
        condition = request.args.get("condition", "").strip().lower()
        year_min = request.args.get("year_min", type=int)
        year_max = request.args.get("year_max", type=int)
        km_max = request.args.get("km_max", type=int)
        q = request.args.get("q", "").strip().lower()

        filtered = cars
        if make:
            filtered = [c for c in filtered if c["make"].lower() == make]
        if fuel:
            filtered = [c for c in filtered if c["fuel_type"].lower() == fuel]
        if condition:
            filtered = [c for c in filtered if c["condition"].lower() == condition]
        if year_min:
            filtered = [c for c in filtered if (c["built_year"] or 0) >= year_min]
        if year_max:
            filtered = [c for c in filtered if (c["built_year"] or 9999) <= year_max]
        if km_max:
            filtered = [c for c in filtered if (c["mileage"] or 0) <= km_max]
        if q:
            filtered = [
                c for c in filtered
                if q in (c["make"] + " " + c["model"] + " " + c["stock_number"]).lower()
            ]

        brands = sorted({c["make"] for c in cars if c["make"]})
        fuels = sorted({c["fuel_type"] for c in cars if c["fuel_type"]})

        return jsonify({"cars": filtered, "total": len(filtered), "brands": brands, "fuels": fuels})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/cars/<stock_number>")
def api_get_car(stock_number):
    try:
        car = get_car_by_stock(stock_number)
        if not car:
            return jsonify({"error": "Carro não encontrado"}), 404
        return jsonify(car)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Routes: Merchants ─────────────────────────────────────────────────────────

@app.get("/api/merchants")
def api_merchants():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        safe_q = q.upper().replace("'", "''")
        sql = f"""
            SELECT id, company
            FROM wkda_dm_es.merchants
            WHERE country='PT' AND status=1
              AND UPPER(company) LIKE '%{safe_q}%'
            ORDER BY company
            LIMIT 20
        """
        rows = run_redash_query(sql, max_age=3600)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Routes: Recommendations ───────────────────────────────────────────────────

@app.post("/api/recommendations")
def api_save_recommendation():
    data = request.get_json(force=True)
    pvp = float(data.get("pvp_ideal") or 0)
    svc = float(data.get("service_costs") or 0)
    trp = float(data.get("transport") or 0)
    obra = float(data.get("obra") or 0)
    margin = float(data.get("margin") or 0)
    ideal = pvp - svc - trp - obra - margin
    a1price = float(data.get("auto1_price") or 0)
    diff = a1price - ideal

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("""
        INSERT INTO recommendations
          (stock_number, make, model, built_year, mileage, auto1_price,
           pvp_ideal, service_costs, transport, obra, margin, ideal_buy_price,
           difference, client_id, client_name, am_name, message, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("stock_number"), data.get("make"), data.get("model"),
        data.get("built_year"), data.get("mileage"), a1price,
        pvp, svc, trp, obra, margin, ideal, diff,
        data.get("client_id"), data.get("client_name"),
        data.get("am_name"), data.get("message"),
        datetime.now().isoformat(),
    ))
    rec_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"id": rec_id, "ideal_buy_price": ideal, "difference": diff})


@app.get("/api/recommendations")
def api_list_recommendations():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── Serve frontend ────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
