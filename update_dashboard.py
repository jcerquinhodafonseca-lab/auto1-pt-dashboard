#!/usr/bin/env python3
"""
Rebuilds TEAMS / ML / MONTHS / CLIENT_DATA / VIEWS_DATA / CLIENT_LIFECYCLE in
index.html from 6 Redash queries. Run this instead of hand-editing the dashboard.

The AM -> team-lead / color roster below is organizational metadata that is
not stored anywhere in the BI warehouse (confirmed: none of the queries used
here, nor the drafts that preceded them, carry a team-lead field) — it only
changes when people join/leave/move teams, so it lives here as a small static
table. Every number (units, calls, claims, views, MTD) is fetched fresh from
Redash on every run.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date

REDASH_URL = "https://dash.prod.bi.auto1.team"
API_KEY = os.environ.get("REDASH_API_KEY")
INDEX_HTML = "index.html"

Q_PURCHASES = 130056
Q_CALLS = 130053
Q_CLAIMS = 130088
Q_VIEWS = 131528
Q_DAILY = 134517
Q_LIFECYCLE = 135246
Q_LIFECYCLE_MONTHLY = 135275

if not API_KEY:
    sys.exit("REDASH_API_KEY environment variable is not set.")

# AM full name -> (team lead, team color). Update when the roster changes.
AM_TEAM = {
    "Joao Paulo Bernardo": ("Pedro Ribeiro", "#FF5C00"),
    "Mario Jorge Cruz": ("Pedro Ribeiro", "#FF5C00"),
    "Marco Aurelio Silva": ("Pedro Ribeiro", "#FF5C00"),
    "Afonso Miguel Silva": ("Pedro Ribeiro", "#FF5C00"),
    "Nuno Brito Vinhas": ("Pedro Ribeiro", "#FF5C00"),
    "Bruno Pardal Rodrigues": ("Pedro Ribeiro", "#FF5C00"),
    "Francisco Sousa Oliveira": ("Pedro Ribeiro", "#FF5C00"),
    "Pedro Miguel Nunes": ("Pedro Ribeiro", "#FF5C00"),
    "Afonso Coelho Ribeiro": ("Pedro Ribeiro", "#FF5C00"),
    "Filipe Mota Mendes": ("Pedro Ribeiro", "#FF5C00"),
    "Mario Sanches Furtado": ("Pedro Ribeiro", "#FF5C00"),
    "Guilherme Santos Silva": ("Pedro Ribeiro", "#FF5C00"),
    "Marta Trincao Oliveira": ("Diogo Fernandes", "#003C7E"),
    "Rafael Goncalo Martins": ("Diogo Fernandes", "#003C7E"),
    "Julio Cesar Damasio": ("Diogo Fernandes", "#003C7E"),
    "Sergio Teixeira Pinto": ("Diogo Fernandes", "#003C7E"),
    "Rute Silva Dias": ("Diogo Fernandes", "#003C7E"),
    "Ariana Pinheiro Franca": ("Diogo Fernandes", "#003C7E"),
    "Fabio Alexandre Pontes": ("Diogo Fernandes", "#003C7E"),
    "Rodrigo Alves Cardoso": ("Diogo Fernandes", "#003C7E"),
    "Leticia Guimaraes Oliveira": ("Diogo Fernandes", "#003C7E"),
    "Irallys Goncalves Fernandes": ("Diogo Fernandes", "#003C7E"),
    "Andre Lopes Nunes": ("Diogo Fernandes", "#003C7E"),
    "Diogo Rodrigues Gomes": ("Diogo Fernandes", "#003C7E"),
    "Mario Jose da Fonseca": ("Diogo Ferreira", "#7C3AED"),
    "Tiago Samuel Duarte": ("Diogo Ferreira", "#7C3AED"),
    "Daniel Lima Barros": ("Diogo Ferreira", "#7C3AED"),
    "Ana Beatriz Alegre": ("Diogo Ferreira", "#7C3AED"),
    "Carlos Alberto Leite": ("Diogo Ferreira", "#7C3AED"),
    "Ricardo Fonseca Flores": ("Diogo Ferreira", "#7C3AED"),
    "Gilberto Micael Castro": ("Diogo Ferreira", "#7C3AED"),
    "Rodrigo Fernandes Tello": ("Diogo Ferreira", "#7C3AED"),
    "Francisco Cerca Goncalves": ("Diogo Ferreira", "#7C3AED"),
    "Martim Marques Vicente": ("Diogo Ferreira", "#7C3AED"),
    "Duarte Monteiro Ribeiro": ("Diogo Ferreira", "#7C3AED"),
    "Catia Cristina Camposana": ("Diogo Ferreira", "#7C3AED"),
    "Lucas Antunes Camargo": ("Bernardo Fernandes", "#059669"),
    "Joao Ferreira Chaves": ("Bernardo Fernandes", "#059669"),
    "Pedro Miguel Miranda": ("Bernardo Fernandes", "#059669"),
    "Telmo Inacio Feliciano": ("Bernardo Fernandes", "#059669"),
    "Ivan Nunes Rodrigues": ("Bernardo Fernandes", "#059669"),
    "Goncalo Miguel Batista": ("Bernardo Fernandes", "#059669"),
    "Andre Cardoso Silva": ("Bernardo Fernandes", "#059669"),
    "Alexandre Silva Miranda": ("Bernardo Fernandes", "#059669"),
    "Andrei Constantin Peceli": ("Bernardo Fernandes", "#059669"),
    "Pedro Luis Lopes": ("Bernardo Fernandes", "#059669"),
    "Diogo Antunes Mendonca": ("Bernardo Fernandes", "#059669"),
    "Edvalson Graca Aguiar": ("Bernardo Fernandes", "#059669"),
    "Jose de Sousa Teixeira": ("Bruno Borralho", "#DC2626"),
    "Goncalo Nogueira Dos Santos": ("Bruno Borralho", "#DC2626"),
    "Ricardo Almeida Vaz": ("Bruno Borralho", "#DC2626"),
    "Andre Serra Nunes": ("Bruno Borralho", "#DC2626"),
    "Phillippe Prudente Toledo": ("Bruno Borralho", "#DC2626"),
}


def fetch_rows(query_id):
    req = urllib.request.Request(
        f"{REDASH_URL}/api/queries/{query_id}/results.json",
        headers={"Authorization": f"Key {API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.load(resp)
    return payload["query_result"]["data"]["rows"]


def rolling_24_months(today):
    months = []
    y, m = today.year, today.month
    for _ in range(24):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    return months


def iso(d):
    return d.strftime("%Y-%m-%d")


def label(d):
    return f"{d.strftime('%b')} {d.strftime('%y')}"


today = date.today()
MONTH_DATES = rolling_24_months(today)
MONTHS = [iso(d) for d in MONTH_DATES]
ML = [label(d) for d in MONTH_DATES]
MONTH_INDEX = {m: i for i, m in enumerate(MONTHS)}

print("Fetching Redash queries...")
purchases = fetch_rows(Q_PURCHASES)
calls = fetch_rows(Q_CALLS)
claims = fetch_rows(Q_CLAIMS)
views = fetch_rows(Q_VIEWS)
daily = fetch_rows(Q_DAILY)
lifecycle = fetch_rows(Q_LIFECYCLE)
lifecycle_monthly = fetch_rows(Q_LIFECYCLE_MONTHLY)
print(f"purchases={len(purchases)} calls={len(calls)} claims={len(claims)} "
      f"views={len(views)} daily={len(daily)} lifecycle={len(lifecycle)} "
      f"lifecycle_monthly={len(lifecycle_monthly)} rows")

unknown_ams = set()


def team_for(am_name):
    return AM_TEAM.get(am_name)


# --- per-AM monthly units, per (AM, merchant) monthly units + name ---
am_monthly = {}
client_units = {}  # am_name -> merchant_id -> {"n":..., "u":[24]}
for r in purchases:
    mo = str(r["month"])[:10]
    if mo not in MONTH_INDEX:
        continue
    idx = MONTH_INDEX[mo]
    am = r["am_name"]
    mid = str(r["merchant_id"])
    units = int(r["units"] or 0)

    am_monthly.setdefault(am, [0] * 24)[idx] += units

    c = client_units.setdefault(am, {}).setdefault(mid, {"n": r.get("merchant_name") or "", "u": [0] * 24})
    c["n"] = r.get("merchant_name") or c["n"]
    c["u"][idx] += units

# --- per-AM monthly calls, per (AM, merchant) monthly calls ---
am_calls_monthly = {}
client_calls = {}  # am_name -> merchant_id -> [24]
for r in calls:
    mo = str(r["month"])[:10]
    if mo not in MONTH_INDEX:
        continue
    idx = MONTH_INDEX[mo]
    am = r["am_name"]
    mid = str(r["merchant_id"])
    total_calls = int(r["total_calls"] or 0)

    am_calls_monthly.setdefault(am, [0] * 24)[idx] += total_calls
    client_calls.setdefault(am, {}).setdefault(mid, [0] * 24)[idx] += total_calls

# --- claims, grouped by (am_name, merchant_id) ---
client_claims = {}  # am_name -> merchant_id -> [claim, ...]
for r in claims:
    am = r.get("am_name") or "Desconhecido"
    mid = str(r["merchant_id"])
    claim = {
        "dt": str(r["claim_date"])[:10] if r.get("claim_date") else "",
        "cn": r.get("claim_number") or "",
        "cs": r.get("claim_status") or "",
        "car": " ".join(x for x in [r.get("manufacturer"), r.get("model")] if x),
        "sn": r.get("stock_number") or "",
        "lp": r.get("liable_party") or "",
        "amt": float(r["amount"] or 0),
    }
    client_claims.setdefault(am, {}).setdefault(mid, []).append(claim)

# --- views per merchant ---
VIEWS_DATA = {}
for r in views:
    mo = str(r["month"])[:10]
    if mo not in MONTH_INDEX:
        continue
    idx = MONTH_INDEX[mo]
    mid = str(r["merchant_id"])
    VIEWS_DATA.setdefault(mid, [0] * 24)[idx] += int(r["views"] or 0)

# --- daily units per AM, for MTD/daily views ---
am_daily = {}  # am_name -> {"YYYY-MM-DD": units}
for r in daily:
    am = r["am_name"]
    d = str(r["day"])[:10]
    am_daily.setdefault(am, {})[d] = int(r["units"] or 0)

# --- assemble CLIENT_DATA ---
# Only AMs in the known roster are shown, matching the dashboard's current
# scope (the am_pt query filter also matches non-PT-team staff sharing the
# same position_id, e.g. other departments/countries -- these are dropped).
queried_am_names = set(am_monthly) | set(client_units) | set(client_calls) | set(client_claims)
unknown_ams = queried_am_names - set(AM_TEAM)
all_am_names = queried_am_names & set(AM_TEAM)
clients_out = {}
for am in all_am_names:
    merchants = {}
    mids = set(client_units.get(am, {})) | set(client_calls.get(am, {})) | set(client_claims.get(am, {}))
    for mid in mids:
        u = client_units.get(am, {}).get(mid, {}).get("u", [0] * 24)
        n = client_units.get(am, {}).get(mid, {}).get("n", "")
        c = client_calls.get(am, {}).get(mid, [0] * 24)
        k = client_claims.get(am, {}).get(mid, [])
        merchants[mid] = {"n": n, "u": u, "c": c, "k": k}
    clients_out[am] = merchants

CLIENT_DATA = {"months": MONTHS, "clients": clients_out}

# --- assemble TEAMS ---
teams_map = {}  # (tl, color) -> [am dicts]
for am in sorted(all_am_names):
    tl, color = team_for(am)
    monthly = am_monthly.get(am, [0] * 24)
    calls_monthly = am_calls_monthly.get(am, [0] * 24)
    am_obj = {
        "name": am,
        "monthly": monthly,
        "calls_monthly": calls_monthly,
        "total": sum(monthly),
        "trend": 0,  # recomputed client-side via linRegTrend()
        "daily": am_daily.get(am, {}),
    }
    teams_map.setdefault((tl, color), []).append(am_obj)

TEAMS = []
for (tl, color), ams in teams_map.items():
    team_monthly = [sum(am["monthly"][i] for am in ams) for i in range(24)]
    TEAMS.append({
        "tl": tl,
        "color": color,
        "monthly": team_monthly,
        "total": sum(team_monthly),
        "trend": 0,  # recomputed client-side via linRegTrend()
        "ams": ams,
    })
TEAMS.sort(key=lambda t: -t["total"])

# --- assemble CLIENT_LIFECYCLE (one row per am/merchant, from Q_LIFECYCLE) ---
CLIENT_LIFECYCLE = [{
    "am": r["am_name"],
    "mid": str(r["merchant_id"]),
    "n": r.get("merchant_name") or "",
    "last": str(r["last_deal_datetime"])[:10] if r.get("last_deal_datetime") else None,
    "db": bool(r.get("dealer_base")),
    "act": bool(r.get("activation")),
    "react": bool(r.get("reactivation")),
    "a30": bool(r.get("active_last_30_days")),
    "a6m": bool(r.get("active_last_6_months")),
    "i6m": bool(r.get("inactive_last_6_months")),
} for r in lifecycle]

# --- assemble LIFECYCLE_MONTHLY (pre-aggregated, so the monthly history stays
# small: 24 numbers per series instead of ~90k raw client/month rows) ---
seg_keys = ["a30", "a6m", "act", "react", "i6m"]
seg_counts = {k: [0] * 24 for k in seg_keys}
total_counts = [0] * 24
team_active6m_counts = {}  # tl -> [24]
for r in lifecycle_monthly:
    mo = str(r["month"])[:10]
    if mo not in MONTH_INDEX:
        continue
    idx = MONTH_INDEX[mo]
    if r.get("dealer_base"):
        total_counts[idx] += 1
    if r.get("active_last_30_days"):
        seg_counts["a30"][idx] += 1
    if r.get("active_last_6_months"):
        seg_counts["a6m"][idx] += 1
    if r.get("activation"):
        seg_counts["act"][idx] += 1
    if r.get("reactivation"):
        seg_counts["react"][idx] += 1
    if r.get("inactive_last_6_months"):
        seg_counts["i6m"][idx] += 1
    tl_color = team_for(r["am_name"])
    if tl_color and r.get("active_last_6_months"):
        tl = tl_color[0]
        team_active6m_counts.setdefault(tl, [0] * 24)[idx] += 1

LIFECYCLE_MONTHLY = {
    "months": MONTHS,
    "total": total_counts,
    "segments": seg_counts,
    "teams": team_active6m_counts,
}

# --- track individual clients across months, to compute flow metrics that a
# per-month stock count can't show (churn velocity, win-back, retention) ---
client_month_flags = {}  # mid -> {month_idx: {"a6m": bool, "act": bool}}
for r in lifecycle_monthly:
    mo = str(r["month"])[:10]
    if mo not in MONTH_INDEX:
        continue
    idx = MONTH_INDEX[mo]
    mid = str(r["merchant_id"])
    client_month_flags.setdefault(mid, {})[idx] = {
        "a6m": bool(r.get("active_last_6_months")),
        "act": bool(r.get("activation")),
    }

# CHURN_MONTHLY: of clients active (6m) in month idx-1, % no longer active in idx
churned_counts = [0] * 24
active_prior_counts = [0] * 24
for flags in client_month_flags.values():
    for idx in range(1, 24):
        prev, cur = flags.get(idx - 1), flags.get(idx)
        if prev is None or cur is None or not prev["a6m"]:
            continue
        active_prior_counts[idx] += 1
        if not cur["a6m"]:
            churned_counts[idx] += 1

CHURN_MONTHLY = {
    "months": ML[1:],
    "churned": churned_counts[1:],
    "active_prior": active_prior_counts[1:],
    "rate": [
        round(churned_counts[i] / active_prior_counts[i] * 100, 1) if active_prior_counts[i] else 0.0
        for i in range(1, 24)
    ],
}

# WINBACK_RATE: of clients who just churned (a6m True -> False), % that become
# a6m-active again within the next 3/6/12 months
winback_windows = {"3m": 3, "6m": 6, "12m": 12}
winback_eligible = {k: 0 for k in winback_windows}
winback_recovered = {k: 0 for k in winback_windows}
for flags in client_month_flags.values():
    for idx in range(1, 24):
        prev, cur = flags.get(idx - 1), flags.get(idx)
        if prev is None or cur is None or not (prev["a6m"] and not cur["a6m"]):
            continue
        for key, n in winback_windows.items():
            if idx + n > 23:
                continue  # not enough months left in the window to judge this cohort
            winback_eligible[key] += 1
            if any(flags.get(f, {}).get("a6m") for f in range(idx + 1, idx + n + 1)):
                winback_recovered[key] += 1

WINBACK_RATE = {}
for key in winback_windows:
    n = winback_eligible[key]
    WINBACK_RATE[f"rate_{key}"] = round(winback_recovered[key] / n * 100, 1) if n else 0.0
    WINBACK_RATE[f"n_{key}"] = n

# RETENTION_CURVE: of clients activated in month idx, % still a6m-active at idx+offset
retention_offsets = list(range(1, 12))
retention_eligible = {o: 0 for o in retention_offsets}
retention_retained = {o: 0 for o in retention_offsets}
for flags in client_month_flags.values():
    for act_idx in (idx for idx, f in flags.items() if f["act"]):
        for offset in retention_offsets:
            future = flags.get(act_idx + offset)
            if future is None:
                continue
            retention_eligible[offset] += 1
            if future["a6m"]:
                retention_retained[offset] += 1

RETENTION_CURVE = {
    "offsets": retention_offsets,
    "pct": [
        round(retention_retained[o] / retention_eligible[o] * 100, 1) if retention_eligible[o] else 0.0
        for o in retention_offsets
    ],
    "n": [retention_eligible[o] for o in retention_offsets],
}

if unknown_ams:
    print(f"NOTE: {len(unknown_ams)} name(s) matched the Redash am_pt filter but are not "
          f"in the AM_TEAM roster (other departments/countries sharing the same position_id, "
          f"or a new hire) -- excluded from the dashboard: {sorted(unknown_ams)}")

# --- write into index.html ---
with open(INDEX_HTML, encoding="utf-8") as f:
    html = f.read()

def replace_const_line(html, name, value_json):
    pattern = re.compile(rf'^const {name} = .*?;.*$', re.MULTILINE)
    new_line = f"const {name} = {value_json};"
    new_html, count = pattern.subn(lambda m: new_line, html, count=1)
    if count != 1:
        sys.exit(f"Could not find exactly one 'const {name} = ...;' line (found {count}).")
    return new_html

html = replace_const_line(html, "TEAMS", json.dumps(TEAMS, ensure_ascii=False))
html = replace_const_line(html, "ML", json.dumps(ML, ensure_ascii=False))
html = replace_const_line(html, "MONTHS", json.dumps(MONTHS, ensure_ascii=False))
html = replace_const_line(html, "CLIENT_DATA", json.dumps(CLIENT_DATA, ensure_ascii=False))
html = replace_const_line(html, "VIEWS_DATA", json.dumps(VIEWS_DATA, ensure_ascii=False))
html = replace_const_line(html, "CLIENT_LIFECYCLE", json.dumps(CLIENT_LIFECYCLE, ensure_ascii=False))
html = replace_const_line(html, "LIFECYCLE_MONTHLY", json.dumps(LIFECYCLE_MONTHLY, ensure_ascii=False))
html = replace_const_line(html, "CHURN_MONTHLY", json.dumps(CHURN_MONTHLY, ensure_ascii=False))
html = replace_const_line(html, "WINBACK_RATE", json.dumps(WINBACK_RATE, ensure_ascii=False))
html = replace_const_line(html, "RETENTION_CURVE", json.dumps(RETENTION_CURVE, ensure_ascii=False))

# Replace hardcoded cutoff dates with a dynamic reference to the last
# generated month, so future runs never need a manual date edit.
before = html
html = html.replace("'2026-05-01'", "MONTHS[MONTHS.length-1]")
if html == before:
    print("NOTE: no hardcoded month-cutoff literal found to replace (already dynamic?).")

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Updated {INDEX_HTML}: {len(TEAMS)} teams, {len(all_am_names)} AMs, "
      f"{sum(len(v) for v in clients_out.values())} client records, "
      f"{len(VIEWS_DATA)} merchants with views, "
      f"{len(CLIENT_LIFECYCLE)} lifecycle records, "
      f"{len(lifecycle_monthly)} monthly lifecycle rows aggregated into 24-month history.")
