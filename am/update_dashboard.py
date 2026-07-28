#!/usr/bin/env python3
"""
Rebuilds ALL_CARS in am/index.html from the Redash query "PT Catalog -
Available Cars" (id 134776). Run this instead of hand-editing the catalog.

Login, proposal submission/history, and the "Vendas" panel are untouched --
they read/write a real Supabase table (per-AM identity, who-submitted-what)
that Redash (read-only BI) cannot serve. Only the static car listing moves
to Redash.
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

REDASH_URL = "https://dash.prod.bi.auto1.team"
API_KEY = os.environ.get("REDASH_API_KEY")
INDEX_HTML = "index.html"
Q_CATALOG = 134776

if not API_KEY:
    sys.exit("REDASH_API_KEY environment variable is not set.")

FUEL_MAP = {
    "Benzin": "Gasolina", "benzin": "Gasolina",
    "Diesel": "Diesel", "diesel": "Diesel",
    "Hybrid": "Híbrido", "hybrid": "Híbrido",
    "Elektro": "Elétrico", "elektro": "Elétrico",
    "Gas": "Gas",
}

# Maps wkda_dm_es.ref_attribute_values.value (joined on car_details.gear_type)
# to the labels used by the TRANS filter/display array in index.html.
GEAR_MAP = {
    "Gear type manual": "Manual",
    "Gear type automatic": "Automático",
    "Semi-automatic": "Semi-Automático",
    "duplex": "Duplex",
}


def api_request(path, method="GET"):
    req = urllib.request.Request(
        f"{REDASH_URL}{path}",
        headers={"Authorization": f"Key {API_KEY}"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def fetch_rows(query_id):
    try:
        payload = api_request(f"/api/queries/{query_id}/results.json")
        return payload["query_result"]["data"]["rows"]
    except urllib.error.HTTPError:
        pass
    job = api_request(f"/api/queries/{query_id}/refresh", method="POST")["job"]
    job_id = job["id"]
    while True:
        job = api_request(f"/api/jobs/{job_id}")["job"]
        if job["status"] == 3:
            break
        if job["status"] == 4:
            sys.exit(f"Query {query_id} refresh failed: {job.get('error')}")
        time.sleep(3)
    result = api_request(f"/api/query_results/{job['query_result_id']}.json")
    return result["query_result"]["data"]["rows"]


def normalize(row):
    fuel = FUEL_MAP.get(row.get("fuel_type") or "", row.get("fuel_type") or "")
    acc = row.get("car_attr_accident_bool")
    orig = row.get("country_of_registration")
    gear = GEAR_MAP.get(row.get("gear_type_value") or "", row.get("gear_type_value") or "")
    return {
        "s": row.get("stock_number") or "",
        "mk": row.get("make") or "",
        "mo": row.get("model") or "",
        "y": row.get("built_year"),
        "km": row.get("mileage"),
        "f": fuel,
        "c": "Não acidentado" if acc == 0 else ("Acidentado" if acc == 1 else "Desconhecido"),
        "o": "Nacional" if orig == "PT" else ("Importado" if orig else "Desconhecido"),
        "p": row.get("auto1_price_eur"),
        "b": row.get("branch_name") or "",
        "t": gear,
        "sr": row.get("seats"),
    }


print("Fetching Redash catalog query...")
rows = fetch_rows(Q_CATALOG)
cars = [normalize(r) for r in rows]
print(f"catalog={len(cars)} rows")

with open(INDEX_HTML, encoding="utf-8") as f:
    html = f.read()

pattern = re.compile(r'^const ALL_CARS\s*=.*?;$', re.MULTILINE)
new_line = f"const ALL_CARS  = {json.dumps(cars, ensure_ascii=False)};"
html, count = pattern.subn(lambda m: new_line, html, count=1)
if count != 1:
    sys.exit(f"Could not find exactly one 'const ALL_CARS = ...;' line (found {count}).")

gen_date = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
html, count = re.subn(r"const GEN_DATE\s*=\s*'.*?';", f"const GEN_DATE     = '{gen_date}';", html, count=1)
if count != 1:
    sys.exit(f"Could not find exactly one 'const GEN_DATE = ...;' line (found {count}).")

html, count = re.subn(
    r'(<span class="gen-date" id="gen-date-hdr">Catálogo: ).*?(</span>)',
    lambda m: f"{m.group(1)}{gen_date}{m.group(2)}",
    html, count=1,
)
if count != 1:
    sys.exit(f"Could not find exactly one gen-date-hdr span (found {count}).")

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Updated {INDEX_HTML}: {len(cars)} cars, generated {gen_date}.")
