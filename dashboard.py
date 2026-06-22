#!/usr/bin/env python3
"""
Auto1 Portugal — Dashboard AM
Corre este ficheiro: python dashboard.py
Abre no browser: http://localhost:5000
Não precisa instalar nada além de Python 3.
"""
import json, time, threading, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.parse import urlencode, parse_qs, urlparse
from urllib.error import HTTPError, URLError

# ── Configuração ──────────────────────────────────────────────────────────────
REDASH_BASE = "https://dash.prod.bi.auto1.team"
REDASH_KEY  = "Cbw7xonVpyBrDWTf09oLhFvCwdTS5EYv32iK7avK"
REDASH_DS   = 89
PORT        = 5000

FUEL_MAP = {
    "Benzin": "Gasolina", "benzin": "Gasolina",
    "Diesel": "Diesel",   "diesel": "Diesel",
    "Hybrid": "Híbrido",  "hybrid": "Híbrido",
    "Elektro": "Elétrico","elektro": "Elétrico",
    "Gas": "Gas",
}

# ── Cache simples em memória ───────────────────────────────────────────────────
_cache = {"cars": None, "ts": 0}
_CACHE_TTL = 3600

# ── Helpers Redash ─────────────────────────────────────────────────────────────
def redash_post(sql, max_age=3600):
    payload = json.dumps({
        "data_source_id": REDASH_DS,
        "query": sql,
        "max_age": max_age
    }).encode()
    req = Request(
        f"{REDASH_BASE}/api/query_results",
        data=payload,
        headers={"Authorization": f"Key {REDASH_KEY}", "Content-Type": "application/json"}
    )
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def redash_get(path):
    req = Request(
        f"{REDASH_BASE}{path}",
        headers={"Authorization": f"Key {REDASH_KEY}"}
    )
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def run_query(sql, max_age=3600):
    resp = redash_post(sql, max_age)
    if "query_result" in resp:
        return resp["query_result"]["data"]["rows"]
    if "job" not in resp:
        raise RuntimeError(f"Resposta inesperada: {list(resp.keys())}")
    job_id = resp["job"]["id"]
    for _ in range(30):
        time.sleep(2)
        jr = redash_get(f"/api/jobs/{job_id}")["job"]
        if jr["status"] == 3:
            result_id = jr["result"]
            data = redash_get(f"/api/query_results/{result_id}")
            return data["query_result"]["data"]["rows"]
        if jr["status"] == 4:
            raise RuntimeError(f"Query falhou: {jr.get('error')}")
    raise TimeoutError("Timeout a aguardar resultado")

# ── Lógica de negócio ──────────────────────────────────────────────────────────
def normalize(row):
    fuel = FUEL_MAP.get(row.get("fuel_type") or "", row.get("fuel_type") or "")
    acc  = row.get("car_attr_accident_bool")
    orig = row.get("country_of_registration")
    return {
        "stock_number": row.get("stock_number", ""),
        "make":         row.get("make", ""),
        "model":        row.get("model", ""),
        "built_year":   row.get("built_year"),
        "mileage":      row.get("mileage"),
        "fuel_type":    fuel,
        "condition":    "Não acidentado" if acc == 0 else ("Acidentado" if acc == 1 else "Desconhecido"),
        "origin":       "Nacional" if orig == "PT" else ("Importado" if orig else "Desconhecido"),
        "auto1_price":  row.get("auto1_price_eur"),
        "branch":       row.get("branch_name", ""),
        "url":          f"https://www.auto1.com/pt/app/merchant/car/{row.get('stock_number','')}",
    }

def get_all_cars():
    now = time.time()
    if _cache["cars"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["cars"]
    sql = """
        SELECT wl.stock_number, wl.make, wl.model, wl.built_year, wl.mileage,
               wl.fuel_type, wl.branch_name,
               cd.car_attr_accident_bool, cd.country_of_registration,
               ROUND(ccp.amount / 100.0, 0) AS auto1_price_eur
        FROM wkda_dm_es.wkda_leads wl
        LEFT JOIN wkda_dm_es.car_details cd ON cd.id = wl.car_id
        LEFT JOIN wkda_dm_es.car_current_prices ccp
          ON ccp.car_id = wl.car_id AND ccp.type = 'auto1_price'
        WHERE wl.country = 'PT' AND wl.lead_status_id = 6
        ORDER BY wl.submitted_at DESC
    """
    rows = run_query(sql, max_age=3600)
    cars = [normalize(r) for r in rows]
    _cache["cars"] = cars
    _cache["ts"]   = now
    return cars

def get_car(stock):
    sql = f"""
        SELECT wl.stock_number, wl.make, wl.model, wl.built_year, wl.mileage,
               wl.fuel_type, wl.branch_name, wl.dat_ecode,
               cd.car_attr_accident_bool, cd.country_of_registration,
               cd.first_registration_date, cd.vin,
               cl.car_type_id,
               rct.mtype_detail, rct.subtype_annex, rct.kw, rct.horsepower,
               ROUND(ccp.amount / 100.0, 0) AS auto1_price_eur
        FROM wkda_dm_es.wkda_leads wl
        LEFT JOIN wkda_dm_es.car_details cd ON cd.id = wl.car_id
        LEFT JOIN wkda_dm_es.car_leads cl ON cl.id = wl.car_id
        LEFT JOIN wkda_dm_es.ref_car_types rct ON rct.id = cl.car_type_id
        LEFT JOIN wkda_dm_es.car_current_prices ccp
          ON ccp.car_id = wl.car_id AND ccp.type = 'auto1_price'
        WHERE wl.stock_number = '{stock.upper().replace("'","")}'
    """
    rows = run_query(sql, max_age=0)
    if not rows:
        return None
    row = rows[0]
    parts = []
    if row.get("mtype_detail"):
        v = row["mtype_detail"].replace(f"{row.get('make','')} {row.get('model','')}", "").strip()
        if v:
            parts.append(v)
    if row.get("subtype_annex"):
        parts.append(row["subtype_annex"])
    car = normalize(row)
    car["version"]                = " ".join(p for p in parts if p)
    car["kw"]                     = row.get("kw")
    car["horsepower"]             = row.get("horsepower")
    car["vin"]                    = row.get("vin")
    car["first_registration_date"]= row.get("first_registration_date")
    return car

def search_merchants(q):
    safe = q.upper().replace("'","")
    sql = f"""
        SELECT id, company FROM wkda_dm_es.merchants
        WHERE country='PT' AND status=1 AND UPPER(company) LIKE '%{safe}%'
        ORDER BY company LIMIT 20
    """
    return run_query(sql, max_age=3600)

# ── Base de dados SQLite simples para histórico ───────────────────────────────
import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), "recommendations.db")

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_number TEXT, make TEXT, model TEXT, built_year INTEGER, mileage INTEGER,
            auto1_price REAL, pvp_ideal REAL, service_costs REAL, transport REAL,
            obra REAL, margin REAL, ideal_buy_price REAL, difference REAL,
            client_id TEXT, client_name TEXT, am_name TEXT, message TEXT, created_at TEXT
        )
    """)
    conn.commit(); conn.close()

def save_rec(data):
    from datetime import datetime
    pvp  = float(data.get("pvp_ideal") or 0)
    svc  = float(data.get("service_costs") or 0)
    trp  = float(data.get("transport") or 0)
    obra = float(data.get("obra") or 0)
    mg   = float(data.get("margin") or 0)
    ideal = pvp - svc - trp - obra - mg
    a1p  = float(data.get("auto1_price") or 0)
    diff = a1p - ideal
    conn = sqlite3.connect(DB)
    c = conn.execute("""
        INSERT INTO recommendations
          (stock_number,make,model,built_year,mileage,auto1_price,pvp_ideal,
           service_costs,transport,obra,margin,ideal_buy_price,difference,
           client_id,client_name,am_name,message,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.get("stock_number"),data.get("make"),data.get("model"),
          data.get("built_year"),data.get("mileage"),a1p,
          pvp,svc,trp,obra,mg,ideal,diff,
          data.get("client_id"),data.get("client_name"),
          data.get("am_name"),data.get("message"),
          datetime.now().isoformat()))
    rid = c.lastrowid; conn.commit(); conn.close()
    return {"id": rid, "ideal_buy_price": ideal, "difference": diff}

def list_recs():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]

init_db()

# ── Servidor HTTP ──────────────────────────────────────────────────────────────
def json_resp(handler, code, obj):
    body = json.dumps(obj, default=str).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path
        qs   = parse_qs(p.query)

        if path == "/" or path == "/index.html":
            self._serve_html()
        elif path == "/api/cars":
            try:
                cars = get_all_cars()
                q    = (qs.get("q", [""])[0]).lower()
                make = (qs.get("make", [""])[0]).lower()
                fuel = (qs.get("fuel", [""])[0]).lower()
                cond = (qs.get("condition", [""])[0]).lower()
                filtered = cars
                if make:   filtered = [c for c in filtered if c["make"].lower() == make]
                if fuel:   filtered = [c for c in filtered if c["fuel_type"].lower() == fuel]
                if cond:   filtered = [c for c in filtered if c["condition"].lower() == cond]
                if q:      filtered = [c for c in filtered if q in (c["make"]+" "+c["model"]+" "+c["stock_number"]+" "+c["branch"]).lower()]
                brands = sorted({c["make"] for c in cars if c["make"]})
                fuels  = sorted({c["fuel_type"] for c in cars if c["fuel_type"]})
                json_resp(self, 200, {"cars": filtered, "total": len(filtered), "brands": brands, "fuels": fuels})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})

        elif path.startswith("/api/cars/"):
            stock = path.split("/api/cars/")[1]
            try:
                car = get_car(stock)
                if car: json_resp(self, 200, car)
                else:   json_resp(self, 404, {"error": "Carro não encontrado"})
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})

        elif path == "/api/merchants":
            q = (qs.get("q", [""])[0]).strip()
            if len(q) < 2:
                json_resp(self, 200, [])
            else:
                try:
                    json_resp(self, 200, search_merchants(q))
                except Exception as e:
                    json_resp(self, 500, {"error": str(e)})

        elif path == "/api/recommendations":
            try:
                json_resp(self, 200, list_recs())
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/api/recommendations":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            try:
                result = save_rec(body)
                json_resp(self, 200, result)
            except Exception as e:
                json_resp(self, 500, {"error": str(e)})
        else:
            self.send_response(404); self.end_headers()

    def _serve_html(self):
        html = HTML_PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html)

# ── Frontend HTML (embutido) ───────────────────────────────────────────────────
HTML_PAGE = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Auto1 PT — Dashboard AM</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;font-size:14px;background:#f4f5f7;color:#1a1a2e}
a{color:#e63946;text-decoration:none}a:hover{text-decoration:underline}
header{background:#1a1a2e;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:16px}
header h1{font-size:18px;font-weight:700}
header span{font-size:12px;opacity:.6;margin-left:auto}
.container{max-width:1400px;margin:0 auto;padding:24px}
.tabs{display:flex;gap:0;border-bottom:2px solid #e0e0e0;margin-bottom:24px}
.tab{padding:10px 20px;cursor:pointer;font-weight:600;color:#666;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all .15s}
.tab.active{color:#e63946;border-bottom-color:#e63946}
.tab:hover:not(.active){color:#333}
.view{display:none}.view.active{display:block}
.search-bar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
.search-bar input,.search-bar select{padding:9px 14px;border:1px solid #ddd;border-radius:6px;font-size:14px;background:#fff;min-width:160px}
.search-bar input:focus,.search-bar select:focus{outline:none;border-color:#e63946}
.btn{padding:9px 18px;border-radius:6px;border:none;cursor:pointer;font-size:14px;font-weight:600;transition:background .15s}
.btn-primary{background:#e63946;color:#fff}.btn-primary:hover{background:#c62828}
.btn-secondary{background:#eee;color:#333}.btn-secondary:hover{background:#ddd}
.btn-green{background:#2e7d32;color:#fff}.btn-green:hover{background:#1b5e20}
.btn-wa{background:#25d366;color:#fff}.btn-wa:hover{background:#128c7e}
.btn-sm{padding:5px 12px;font-size:13px}
.stats{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}
.stat{background:#fff;border-radius:8px;padding:14px 20px;flex:1;min-width:140px;border:1px solid #e8e8e8}
.stat .num{font-size:26px;font-weight:700;color:#e63946}
.stat .lbl{font-size:12px;color:#888;margin-top:2px}
.table-wrap{background:#fff;border-radius:8px;border:1px solid #e8e8e8;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{padding:10px 14px;text-align:left;font-weight:600;opacity:.65;font-size:13px;background:#fafafa;border-bottom:1px solid #eee;white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid #f0f0f0;font-size:13px}
tr:last-child td{border-bottom:none}tr:hover td{background:#fafafa}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
.badge-ok{background:#e8f5e9;color:#2e7d32}.badge-warn{background:#fff3e0;color:#e65100}
.badge-neutral{background:#e3f2fd;color:#1565c0}.badge-gray{background:#f5f5f5;color:#666}
.pagination{padding:12px 16px;display:flex;align-items:center;gap:12px;border-top:1px solid #f0f0f0}
.pag-btn{padding:4px 12px;border:1px solid #ddd;border-radius:4px;background:#fff;cursor:pointer;font-size:13px}
.pag-btn:disabled{opacity:.35;cursor:default}
.pag-info{font-size:13px;color:#666;flex:1;text-align:center}
.detail-layout{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media(max-width:900px){.detail-layout{grid-template-columns:1fr}}
.card{background:#fff;border-radius:8px;border:1px solid #e8e8e8;padding:20px;margin-bottom:16px}
.card h3{font-size:16px;font-weight:700;margin-bottom:16px;color:#1a1a2e;border-bottom:1px solid #f0f0f0;padding-bottom:10px}
.info-row{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f9f9f9}
.info-row:last-child{border-bottom:none}
.info-label{color:#888;font-size:13px}.info-value{font-weight:600;font-size:13px;text-align:right}
.calc-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
.calc-row label{font-size:13px;color:#555;align-self:center}
.calc-row input{padding:7px 10px;border:1px solid #ddd;border-radius:5px;font-size:14px;width:100%}
.calc-row input:focus{outline:none;border-color:#e63946}
.calc-result{background:#1a1a2e;color:#fff;border-radius:6px;padding:14px;margin-top:12px}
.calc-result .total{font-size:20px;font-weight:700}
.calc-result .diff{font-size:13px;margin-top:4px;opacity:.85}
.diff-green{color:#66bb6a}.diff-red{color:#ef5350}
.msg-box{background:#f9f9f9;border:1px solid #e0e0e0;border-radius:8px;padding:16px;font-size:13px;white-space:pre-wrap;line-height:1.7;min-height:120px;color:#222}
.msg-actions{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.history-item{background:#fff;border-radius:8px;border:1px solid #e8e8e8;padding:16px;margin-bottom:12px}
.history-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
.history-car{font-weight:700;font-size:15px}.history-meta{font-size:12px;color:#888}
.history-client{font-size:13px;color:#555;margin-bottom:6px}
.history-msg{font-size:12px;color:#777;background:#f5f5f5;padding:8px;border-radius:4px;white-space:pre-wrap;max-height:80px;overflow:hidden}
.client-search{position:relative}
.client-dropdown{position:absolute;top:100%;left:0;right:0;background:#fff;border:1px solid #ddd;border-radius:5px;max-height:200px;overflow-y:auto;z-index:10;display:none;box-shadow:0 4px 16px rgba(0,0,0,.1)}
.client-option{padding:9px 12px;cursor:pointer;font-size:13px}
.client-option:hover{background:#f5f5f5}
.client-option .opt-id{font-size:11px;color:#aaa;margin-left:8px}
.loading{text-align:center;padding:40px;color:#888}
.error-msg{background:#ffebee;color:#c62828;padding:12px 16px;border-radius:6px;margin-bottom:16px}
</style>
</head>
<body>
<header>
  <div style="background:#e63946;border-radius:6px;padding:4px 10px;font-weight:700;font-size:13px">A1</div>
  <h1>Auto1 Portugal — Dashboard AM</h1>
  <span id="am-name-display"></span>
</header>
<div class="container">
  <div id="am-setup" style="background:#fff;border-radius:8px;border:1px solid #e8e8e8;padding:24px;max-width:400px;margin:0 auto 24px">
    <h3 style="margin-bottom:12px;font-size:16px">Bem-vindo! Qual é o seu nome?</h3>
    <div style="display:flex;gap:10px">
      <input id="am-name-input" type="text" placeholder="O seu nome (ex: João Silva)"
             style="flex:1;padding:9px 14px;border:1px solid #ddd;border-radius:6px;font-size:14px"/>
      <button class="btn btn-primary" onclick="setAmName()">Entrar</button>
    </div>
  </div>
  <div id="main-app" style="display:none">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('browse')">Catálogo PT</div>
      <div class="tab" onclick="switchTab('search')">Pesquisar Carro</div>
      <div class="tab" onclick="switchTab('history')">Histórico</div>
    </div>

    <!-- BROWSE -->
    <div id="tab-browse" class="view active">
      <div class="stats">
        <div class="stat"><div class="num" id="stat-total">—</div><div class="lbl">Carros disponíveis</div></div>
        <div class="stat"><div class="num" id="stat-brands">—</div><div class="lbl">Marcas</div></div>
        <div class="stat"><div class="num" id="stat-recs">—</div><div class="lbl">Recomendações enviadas</div></div>
      </div>
      <div class="search-bar">
        <input id="browse-q" type="text" placeholder="Pesquisar marca, modelo, stock…" oninput="filterCars()" style="flex:2;min-width:200px"/>
        <select id="filter-make" onchange="filterCars()"><option value="">Todas as marcas</option></select>
        <select id="filter-fuel" onchange="filterCars()"><option value="">Todos os combustíveis</option></select>
        <select id="filter-condition" onchange="filterCars()">
          <option value="">Qualquer condição</option>
          <option value="não acidentado">Não acidentado</option>
          <option value="acidentado">Acidentado</option>
        </select>
        <button class="btn btn-secondary btn-sm" onclick="resetFilters()">Limpar</button>
      </div>
      <div id="browse-loading" class="loading">A carregar catálogo…</div>
      <div id="browse-error" class="error-msg" style="display:none"></div>
      <div id="browse-table" style="display:none">
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>Stock</th><th>Marca</th><th>Modelo</th><th>Ano</th>
              <th>Km</th><th>Combustível</th><th>Condição</th>
              <th>Origem</th><th>Preço Auto1</th><th>Localização</th><th></th>
            </tr></thead>
            <tbody id="cars-tbody"></tbody>
          </table>
          <div class="pagination">
            <button class="pag-btn" id="pag-prev" onclick="changePage(-1)" disabled>← Anterior</button>
            <span class="pag-info" id="pag-info"></span>
            <button class="pag-btn" id="pag-next" onclick="changePage(1)">Próximo →</button>
          </div>
        </div>
      </div>
    </div>

    <!-- SEARCH -->
    <div id="tab-search" class="view">
      <div class="search-bar" style="max-width:500px">
        <input id="stock-input" type="text" placeholder="Nº do carro (ex: HA23712)"
               style="flex:1;text-transform:uppercase" maxlength="12"
               onkeydown="if(event.key==='Enter') searchCar()"/>
        <button class="btn btn-primary" onclick="searchCar()">Pesquisar</button>
      </div>
      <div id="search-loading" class="loading" style="display:none">A procurar…</div>
      <div id="search-error" class="error-msg" style="display:none"></div>
      <div id="car-detail" style="display:none"></div>
    </div>

    <!-- HISTORY -->
    <div id="tab-history" class="view">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="font-size:16px;font-weight:700">Histórico de Recomendações</h3>
        <button class="btn btn-secondary btn-sm" onclick="loadHistory()">↻ Atualizar</button>
      </div>
      <div id="history-loading" class="loading" style="display:none">A carregar…</div>
      <div id="history-list"></div>
    </div>
  </div>
</div>
<script>
let allCars=[], filteredCars=[], page=0;
const PAGE_SIZE=25;
let amName=localStorage.getItem("am_name")||"";
let currentCar=null;

window.onload=function(){if(amName)showApp();}

function setAmName(){
  const v=document.getElementById("am-name-input").value.trim();
  if(!v)return;
  amName=v; localStorage.setItem("am_name",v); showApp();
}

function showApp(){
  document.getElementById("am-setup").style.display="none";
  document.getElementById("main-app").style.display="block";
  document.getElementById("am-name-display").textContent=amName;
  loadCars(); loadRecCount();
}

function switchTab(name){
  document.querySelectorAll(".tab").forEach((t,i)=>{
    t.classList.toggle("active",["browse","search","history"][i]===name);
  });
  document.querySelectorAll(".view").forEach(v=>v.classList.remove("active"));
  document.getElementById("tab-"+name).classList.add("active");
  if(name==="history")loadHistory();
}

async function loadCars(){
  document.getElementById("browse-loading").style.display="block";
  document.getElementById("browse-error").style.display="none";
  document.getElementById("browse-table").style.display="none";
  try{
    const res=await fetch("/api/cars");
    const data=await res.json();
    if(data.error)throw new Error(data.error);
    allCars=data.cars; filteredCars=[...allCars];
    document.getElementById("stat-total").textContent=data.total;
    document.getElementById("stat-brands").textContent=data.brands.length;
    const mk=document.getElementById("filter-make");
    data.brands.forEach(b=>{const o=document.createElement("option");o.value=b;o.textContent=b;mk.appendChild(o);});
    const fl=document.getElementById("filter-fuel");
    data.fuels.forEach(f=>{const o=document.createElement("option");o.value=f.toLowerCase();o.textContent=f;fl.appendChild(o);});
    document.getElementById("browse-loading").style.display="none";
    document.getElementById("browse-table").style.display="block";
    renderTable();
  }catch(e){
    document.getElementById("browse-loading").style.display="none";
    document.getElementById("browse-error").style.display="block";
    document.getElementById("browse-error").textContent="Erro a carregar catálogo: "+e.message;
  }
}

async function loadRecCount(){
  try{const r=await fetch("/api/recommendations");const d=await r.json();document.getElementById("stat-recs").textContent=d.length;}catch(e){}
}

function filterCars(){
  const q=document.getElementById("browse-q").value.trim().toLowerCase();
  const make=document.getElementById("filter-make").value.toLowerCase();
  const fuel=document.getElementById("filter-fuel").value.toLowerCase();
  const cond=document.getElementById("filter-condition").value.toLowerCase();
  filteredCars=allCars.filter(c=>{
    if(make&&c.make.toLowerCase()!==make)return false;
    if(fuel&&c.fuel_type.toLowerCase()!==fuel)return false;
    if(cond&&c.condition.toLowerCase()!==cond)return false;
    if(q){const s=(c.make+" "+c.model+" "+c.stock_number+" "+c.branch).toLowerCase();if(!s.includes(q))return false;}
    return true;
  });
  page=0; renderTable();
}

function resetFilters(){
  document.getElementById("browse-q").value="";
  document.getElementById("filter-make").value="";
  document.getElementById("filter-fuel").value="";
  document.getElementById("filter-condition").value="";
  filterCars();
}

function renderTable(){
  const start=page*PAGE_SIZE;
  const slice=filteredCars.slice(start,start+PAGE_SIZE);
  document.getElementById("cars-tbody").innerHTML=slice.map(c=>`
    <tr>
      <td><strong>${c.stock_number}</strong></td><td>${c.make}</td><td>${c.model}</td>
      <td>${c.built_year||"—"}</td>
      <td>${c.mileage?c.mileage.toLocaleString("pt")+" km":"—"}</td>
      <td>${c.fuel_type||"—"}</td>
      <td><span class="badge ${c.condition==="Não acidentado"?"badge-ok":"badge-warn"}">${c.condition}</span></td>
      <td><span class="badge ${c.origin==="Nacional"?"badge-neutral":"badge-gray"}">${c.origin}</span></td>
      <td>${c.auto1_price?"€ "+c.auto1_price.toLocaleString("pt"):"—"}</td>
      <td>${c.branch||"—"}</td>
      <td><button class="btn btn-primary btn-sm" onclick="openCar('${c.stock_number}')">Selecionar</button></td>
    </tr>`).join("");
  const total=filteredCars.length, end=Math.min(start+PAGE_SIZE,total);
  document.getElementById("pag-info").textContent=total===0?"Sem resultados":`${start+1}–${end} de ${total}`;
  document.getElementById("pag-prev").disabled=page===0;
  document.getElementById("pag-next").disabled=end>=total;
}

function changePage(dir){page+=dir;renderTable();window.scrollTo(0,0);}
function openCar(sn){document.getElementById("stock-input").value=sn;switchTab("search");searchCar();}

async function searchCar(){
  const sn=document.getElementById("stock-input").value.trim().toUpperCase();
  if(!sn)return;
  document.getElementById("search-loading").style.display="block";
  document.getElementById("search-error").style.display="none";
  document.getElementById("car-detail").style.display="none";
  try{
    const res=await fetch("/api/cars/"+sn);
    const car=await res.json();
    if(car.error)throw new Error(car.error);
    currentCar=car;
    document.getElementById("search-loading").style.display="none";
    document.getElementById("car-detail").style.display="block";
    renderDetail(car);
  }catch(e){
    document.getElementById("search-loading").style.display="none";
    document.getElementById("search-error").style.display="block";
    document.getElementById("search-error").textContent="Carro não encontrado: "+e.message;
  }
}

function renderDetail(car){
  const v=car.version?` ${car.version}`:"";
  const title=`${car.make} ${car.model}${v}`;
  const a1=car.auto1_price||0;
  document.getElementById("car-detail").innerHTML=`
    <div style="margin-bottom:16px">
      <h2 style="font-size:20px;font-weight:700">${title}</h2>
      <a href="${car.url}" target="_blank" style="font-size:13px">🔗 Ver no Auto1 (${car.stock_number})</a>
    </div>
    <div class="detail-layout">
      <div>
        <div class="card">
          <h3>Informação do Carro</h3>
          ${ir("Marca",car.make)}${ir("Modelo",car.model)}${car.version?ir("Versão",car.version):""}
          ${ir("Ano",car.built_year)}${ir("Quilómetros",car.mileage?car.mileage.toLocaleString("pt")+" km":"—")}
          ${ir("Combustível",car.fuel_type)}
          ${ir("Condição",`<span class="badge ${car.condition==="Não acidentado"?"badge-ok":"badge-warn"}">${car.condition}</span>`)}
          ${ir("Origem",`<span class="badge badge-neutral">${car.origin}</span>`)}
          ${ir("Localização",car.branch)}
          ${car.first_registration_date?ir("1ª Registo",car.first_registration_date):""}
          ${ir("Preço Auto1",`<strong style="color:#e63946">€ ${a1.toLocaleString("pt")}</strong>`)}
        </div>
        <div class="card">
          <h3>Cliente</h3>
          <div style="margin-bottom:12px">
            <label style="font-size:13px;color:#555;display:block;margin-bottom:4px">Pesquisar por nome</label>
            <div class="client-search">
              <input id="cli-search" type="text" placeholder="Nome do stand / cliente…"
                style="width:100%;padding:9px 14px;border:1px solid #ddd;border-radius:6px;font-size:14px"
                oninput="searchClient()" onblur="setTimeout(hideDrop,200)"/>
              <div class="client-dropdown" id="cli-drop"></div>
            </div>
          </div>
          <div class="calc-row"><label>ID do cliente</label><input id="client-id" type="text" placeholder="ID Auto1 (opcional)"/></div>
          <div class="calc-row"><label>Nome (confirmar)</label><input id="client-name" type="text" placeholder="Nome do stand / cliente"/></div>
        </div>
      </div>
      <div>
        <div class="card">
          <h3>Calculadora de Margem</h3>
          <div class="calc-row"><label>PVP Ideal (€)</label><input id="pvp" type="number" placeholder="ex: 14950" oninput="calc()"/></div>
          <div class="calc-row"><label>Custos de Serviço (€)</label><input id="svc" type="number" placeholder="ex: 418" oninput="calc()"/></div>
          <div class="calc-row"><label>Transporte (€)</label><input id="trp" type="number" placeholder="ex: 99" oninput="calc()"/></div>
          <div class="calc-row"><label>Obra (€)</label><input id="obra" type="number" placeholder="ex: 750" oninput="calc()"/></div>
          <div class="calc-row"><label>Margem Bruta (€)</label><input id="margin" type="number" placeholder="ex: 3000" oninput="calc()"/></div>
          <div class="calc-result" id="calc-result" style="display:none">
            <div style="font-size:13px;opacity:.8;margin-bottom:4px">Preço ideal de compra</div>
            <div class="total" id="calc-ideal">—</div>
            <div class="diff" id="calc-diff"></div>
          </div>
        </div>
        <div class="card">
          <h3>Mensagem para WhatsApp</h3>
          <div class="msg-box" id="msg-preview">Preencha a calculadora para gerar a mensagem…</div>
          <div class="msg-actions">
            <button class="btn btn-secondary btn-sm" onclick="copyMsg()">📋 Copiar</button>
            <button class="btn btn-wa btn-sm" onclick="sendWA()">📱 Enviar WhatsApp</button>
            <button class="btn btn-green btn-sm" onclick="saveRec()">💾 Guardar</button>
          </div>
          <div id="save-ok" style="font-size:13px;color:#2e7d32;margin-top:8px;display:none">✓ Guardado!</div>
        </div>
      </div>
    </div>`;
}

function ir(l,v){return `<div class="info-row"><span class="info-label">${l}</span><span class="info-value">${v??'—'}</span></div>`;}

function calc(){
  const pvp=+document.getElementById("pvp")?.value||0;
  const svc=+document.getElementById("svc")?.value||0;
  const trp=+document.getElementById("trp")?.value||0;
  const obra=+document.getElementById("obra")?.value||0;
  const mg=+document.getElementById("margin")?.value||0;
  if(!pvp){document.getElementById("calc-result").style.display="none";updateMsg();return;}
  const ideal=pvp-svc-trp-obra-mg;
  const a1=currentCar?.auto1_price||0;
  const diff=a1-ideal;
  document.getElementById("calc-result").style.display="block";
  document.getElementById("calc-ideal").textContent="€ "+ideal.toLocaleString("pt",{minimumFractionDigits:0,maximumFractionDigits:0});
  if(a1&&Math.abs(diff)>1){
    const abs=Math.abs(diff).toLocaleString("pt",{minimumFractionDigits:0,maximumFractionDigits:0});
    document.getElementById("calc-diff").innerHTML=diff<0
      ?`<span class="diff-green">✓ O nosso está €${abs} mais barato → incrementa margem bruta</span>`
      :`<span class="diff-red">⚠ O nosso está €${abs} acima do preço ideal</span>`;
  }else document.getElementById("calc-diff").textContent="Preço alinhado com o ideal";
  updateMsg();
}

function updateMsg(){
  if(!currentCar)return;
  const car=currentCar;
  const pvp=+document.getElementById("pvp")?.value||0;
  const svc=+document.getElementById("svc")?.value||0;
  const trp=+document.getElementById("trp")?.value||0;
  const obra=+document.getElementById("obra")?.value||0;
  const mg=+document.getElementById("margin")?.value||0;
  const v=car.version?` ${car.version}`:"";
  const title=`${car.make} ${car.model}${v}`;
  const km=car.mileage?car.mileage.toLocaleString("pt")+" km":"—";
  const a1=car.auto1_price||0;
  if(!pvp){document.getElementById("msg-preview").textContent=`${title} - ${car.built_year||"—"} - ${km} - ${car.condition} - ${car.origin}\n\nPreencha a calculadora…`;return;}
  const ideal=pvp-svc-trp-obra-mg;
  const diff=a1-ideal;
  const fmt=n=>"€ "+Math.round(n).toLocaleString("pt");
  let msg=`${title} - ${car.built_year||"—"} - ${km} - ${car.condition} - ${car.origin}\n\n`;
  msg+=`${fmt(pvp)} (PVP ideal)`;
  if(svc)msg+=` - ${fmt(svc)} (Custos de serviço)`;
  if(trp)msg+=` - ${fmt(trp)} (Transporte)`;
  if(obra)msg+=` - ${fmt(obra)} (Obra)`;
  if(mg)msg+=` - ${fmt(mg)} (Margem bruta)`;
  msg+=` = ${fmt(ideal)} (Preço ideal de compra)`;
  if(a1&&Math.abs(diff)>1){
    const abs=Math.abs(diff).toLocaleString("pt",{minimumFractionDigits:0,maximumFractionDigits:0});
    msg+=diff<0?`\nO nosso está €${abs} mais barato, o que incrementa à margem bruta`:`\nO nosso está €${abs} acima do preço ideal de compra`;
  }
  msg+=`\n\n🔗 ${car.url}`;
  document.getElementById("msg-preview").textContent=msg;
}

let _cliTimer=null;
async function searchClient(){
  clearTimeout(_cliTimer);
  const q=document.getElementById("cli-search").value.trim();
  if(q.length<2){hideDrop();return;}
  _cliTimer=setTimeout(async()=>{
    try{
      const r=await fetch("/api/merchants?q="+encodeURIComponent(q));
      const ms=await r.json();
      const d=document.getElementById("cli-drop");
      if(!ms.length){hideDrop();return;}
      d.innerHTML=ms.map(m=>`<div class="client-option" onmousedown="selClient('${m.id}','${m.company.replace(/'/g,"\\'")}')">
        ${m.company}<span class="opt-id">#${m.id}</span></div>`).join("");
      d.style.display="block";
    }catch(e){}
  },300);
}

function selClient(id,name){
  document.getElementById("client-id").value=id;
  document.getElementById("client-name").value=name;
  document.getElementById("cli-search").value=name;
  hideDrop();
}
function hideDrop(){const d=document.getElementById("cli-drop");if(d)d.style.display="none";}

function copyMsg(){
  const msg=document.getElementById("msg-preview")?.textContent||"";
  navigator.clipboard.writeText(msg).then(()=>{const b=event.target;b.textContent="✓ Copiado!";setTimeout(()=>{b.textContent="📋 Copiar";},2000);});
}

function sendWA(){
  const msg=document.getElementById("msg-preview")?.textContent||"";
  window.open("https://web.whatsapp.com/send?text="+encodeURIComponent(msg),"_blank");
}

async function saveRec(){
  if(!currentCar)return;
  const pvp=+document.getElementById("pvp")?.value||0;
  const svc=+document.getElementById("svc")?.value||0;
  const trp=+document.getElementById("trp")?.value||0;
  const obra=+document.getElementById("obra")?.value||0;
  const mg=+document.getElementById("margin")?.value||0;
  const msg=document.getElementById("msg-preview")?.textContent||"";
  const cid=document.getElementById("client-id")?.value||"";
  const cname=document.getElementById("client-name")?.value||"";
  try{
    await fetch("/api/recommendations",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({stock_number:currentCar.stock_number,make:currentCar.make,model:currentCar.model,
        built_year:currentCar.built_year,mileage:currentCar.mileage,auto1_price:currentCar.auto1_price,
        pvp_ideal:pvp,service_costs:svc,transport:trp,obra,margin:mg,
        client_id:cid,client_name:cname,am_name:amName,message:msg})});
    document.getElementById("save-ok").style.display="block";
    setTimeout(()=>{document.getElementById("save-ok").style.display="none";},3000);
    loadRecCount();
  }catch(e){alert("Erro: "+e.message);}
}

async function loadHistory(){
  const el=document.getElementById("history-list");
  document.getElementById("history-loading").style.display="block";
  el.innerHTML="";
  try{
    const r=await fetch("/api/recommendations");
    const recs=await r.json();
    document.getElementById("history-loading").style.display="none";
    if(!recs.length){el.innerHTML='<p style="color:#888;padding:20px">Sem recomendações ainda.</p>';return;}
    el.innerHTML=recs.map(r=>{
      const ideal=r.ideal_buy_price?"€ "+Math.round(r.ideal_buy_price).toLocaleString("pt"):"—";
      const diff=r.difference;
      const ds=diff!=null?(diff<0?`✓ €${Math.abs(Math.round(diff)).toLocaleString("pt")} mais barato`:`⚠ €${Math.round(diff).toLocaleString("pt")} acima`):"";
      return `<div class="history-item">
        <div class="history-header">
          <div><div class="history-car">${r.make} ${r.model} — ${r.stock_number}</div>
          <div class="history-meta">${r.built_year||"—"} · ${r.mileage?r.mileage.toLocaleString("pt")+"km":"—"} · Ideal: ${ideal} ${ds}</div></div>
          <div class="history-meta">${r.am_name||"—"}<br/>${r.created_at?r.created_at.substring(0,16).replace("T"," "):""}</div>
        </div>
        <div class="history-client">👤 ${r.client_name||"—"} ${r.client_id?"(#"+r.client_id+")":""}</div>
        <div class="history-msg">${(r.message||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")}</div>
      </div>`;
    }).join("");
  }catch(e){
    document.getElementById("history-loading").style.display="none";
    el.innerHTML=`<div class="error-msg">Erro: ${e.message}</div>`;
  }
}
</script>
</body>
</html>"""

# ── Arranque ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"""
╔══════════════════════════════════════════╗
║   Auto1 PT — Dashboard AM               ║
╠══════════════════════════════════════════╣
║  A abrir em: {url:<29}║
║  Carrega o catálogo na 1ª vez (~15s)    ║
║  Pressiona Ctrl+C para parar            ║
╚══════════════════════════════════════════╝
""")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")
