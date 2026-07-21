#!/usr/bin/env python3
"""
Generate AUTO1 PT Dashboard (Equipas) with daily data from Redash
"""
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from collections import defaultdict

REDASH_KEY = "Cbw7xonVpyBrDWTf09oLhFvCwdTS5EYv32iK7avK"
REDASH_BASE = "https://dash.prod.bi.auto1.team"
QUERY_ID = 134517  # AM_PT_Dashboard_Daily_Units

def redash_get(path):
    """Fetch from Redash API"""
    req = urllib.request.Request(
        f"{REDASH_BASE}{path}",
        headers={"Authorization": f"Key {REDASH_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Redash API error: {e}")
        return {}

def fetch_daily_data():
    """Fetch daily units data from Redash query"""
    print("Fetching daily data from Redash...")

    # Get query result (use the latest cached result)
    resp = redash_get(f"/api/queries/{QUERY_ID}/results")

    if "query_result" not in resp:
        print(f"Warning: No query result. Response keys: {list(resp.keys())}")
        return {}

    rows = resp["query_result"]["data"]["rows"]

    # Build daily data structure: {am_name: {"2026-01-15": units, ...}}
    daily_data = defaultdict(dict)
    for row in rows:
        am_name = row.get("am_name")
        day = row.get("day")
        units = row.get("units", 0)
        if am_name and day:
            daily_data[am_name][day] = units

    print(f"Loaded {len(daily_data)} AMs with daily data ({len(rows)} rows)")
    return dict(daily_data)

def load_online_dashboard():
    """Load existing online dashboard HTML to extract TEAMS data"""
    print("Loading online dashboard...")
    import urllib.request
    url = "https://jcerquinhodafonseca-lab.github.io/auto1-pt-dashboard/"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error loading online dashboard: {e}")
        return ""

def inject_daily_data(html_content, daily_data):
    """Inject daily data into TEAMS array in HTML"""
    print("Injecting daily data into HTML...")

    # Find TEAMS array in the HTML
    import re
    match = re.search(r'(const TEAMS = \[.*?]\s*;)', html_content, re.DOTALL)
    if not match:
        print("Error: Could not find TEAMS array in HTML")
        return html_content

    teams_old = match.group(1)

    # Parse and modify TEAMS data
    try:
        # Extract just the array part
        array_start = teams_old.find('[')
        array_end = teams_old.rfind(']') + 1
        teams_json_str = teams_old[array_start:array_end]

        teams = json.loads(teams_json_str)

        # Inject daily data
        for team in teams:
            for am in team.get("ams", []):
                am_name = am.get("name")
                if am_name in daily_data:
                    am["daily"] = daily_data[am_name]
                    print(f"  ✓ Injected {len(daily_data[am_name])} daily entries for {am_name}")
                else:
                    print(f"  ⚠ No daily data found for {am_name}")

        # Reconstruct the const statement
        teams_new = f"const TEAMS = {json.dumps(teams, ensure_ascii=False)};"
        html_modified = html_content.replace(teams_old, teams_new)

        return html_modified
    except json.JSONDecodeError as e:
        print(f"Error parsing TEAMS JSON: {e}")
        return html_content

def save_dashboard(html_content, output_path="index_generated.html"):
    """Save modified HTML to file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✓ Dashboard saved to {output_path}")

if __name__ == "__main__":
    # Fetch fresh daily data
    daily_data = fetch_daily_data()

    if not daily_data:
        print("Error: No daily data fetched. Exiting.")
        exit(1)

    # Load existing dashboard
    html = load_online_dashboard()
    if not html:
        print("Error: Could not load online dashboard. Exiting.")
        exit(1)

    # Inject daily data
    html_modified = inject_daily_data(html, daily_data)

    # Save
    save_dashboard(html_modified)
    print("\n✓ Done! MTD should now show correct values (calculated from daily data)")
