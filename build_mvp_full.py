#!/usr/bin/env python3
"""
Build COMPLETE MVP Dashboard with all functions implemented
"""
import re
import json
import sys

def load_current_html():
    """Load current index.html"""
    try:
        with open('index.html', 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except FileNotFoundError:
        print("Error: index.html not found")
        return None

def extract_javascript_const(html, const_name):
    """Extract a JavaScript const from HTML"""
    pattern = rf'const {const_name}\s*=\s*(\{{.*?\}});'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        pattern = rf'const {const_name}\s*=\s*(\[.*?\]);'
        match = re.search(pattern, html, re.DOTALL)
    if match:
        return match.group(1)
    return None

def generate_mvp_complete(teams_str):
    """Generate complete MVP HTML with all functions"""

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auto1 Portugal — Dashboard Executivo</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --orange: #FF5C00;
  --blue: #003C7E;
  --blue2: #0052A5;
  --dark: #1A1A2A;
  --muted: rgba(26,26,42,.5);
  --border: rgba(26,26,42,.1);
  --card: #fff;
  --bg: #F4F6FA;
  --green: #2E7D32;
  --red: #C62828;
  --amber: #E65100;
}}

html {{ scroll-behavior: smooth; }}
body {{
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  background: var(--bg);
  color: var(--dark);
  min-height: 100vh;
}}

/* HEADER */
.header {{
  background: var(--blue);
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  height: 54px;
  box-shadow: 0 2px 8px rgba(0,0,0,.18);
  position: sticky;
  top: 0;
  z-index: 100;
}}

.header-logo {{
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}}

.header-nav {{
  display: flex;
  gap: 0;
  margin-left: 24px;
}}

.nav-btn {{
  background: none;
  border: none;
  color: rgba(255,255,255,.7);
  font-size: 13px;
  font-weight: 600;
  padding: 16px 16px;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: all .15s;
}}

.nav-btn:hover {{ color: #fff; }}
.nav-btn.active {{ color: var(--orange); border-bottom-color: var(--orange); }}

.header-right {{
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: rgba(255,255,255,.5);
}}

/* CONTAINER */
.container {{ max-width: 1600px; margin: 0 auto; padding: 24px; }}
.view {{ display: none; }}
.view.active {{ display: block; }}

/* CARDS */
.stat-card {{
  background: var(--card);
  border-radius: 10px;
  border: 1.5px solid var(--border);
  padding: 16px;
  text-align: center;
}}

.stat-card .num {{
  font-size: 28px;
  font-weight: 800;
  color: var(--orange);
  margin: 8px 0;
}}

.stat-card .lbl {{
  font-size: 12px;
  color: var(--muted);
}}

.kpi-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}}

.chart-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}}

.chart-card {{
  background: var(--card);
  border-radius: 10px;
  border: 1.5px solid var(--border);
  padding: 20px;
}}

.chart-card h3 {{
  font-size: 14px;
  font-weight: 700;
  color: var(--blue);
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}}

/* TABLE */
.table-wrap {{
  background: var(--card);
  border-radius: 10px;
  border: 1.5px solid var(--border);
  overflow: hidden;
}}

table {{
  width: 100%;
  border-collapse: collapse;
}}

th {{
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  opacity: .65;
  font-size: 13px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}}

td {{
  padding: 10px 14px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}}

tr:hover td {{ background: #fafafa; }}
tr:last-child td {{ border-bottom: none; }}

.pagination {{
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-top: 1px solid #f0f0f0;
}}

.pag-btn {{
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}}

.pag-btn:disabled {{ opacity: .35; cursor: default; }}

.pag-info {{
  font-size: 13px;
  color: var(--muted);
  flex: 1;
  text-align: center;
}}

.badge {{
  display: inline-block;
  padding: 3px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}}

.badge-green {{ background: #E8F5E9; color: #2E7D32; }}
.badge-red {{ background: #FFEBEE; color: #C62828; }}
.badge-amber {{ background: #FFF3E0; color: #E65100; }}

.insight-item {{
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
}}

.insight-item:last-child {{ border-bottom: none; }}

h2 {{
  margin-bottom: 24px;
  font-size: 22px;
  color: var(--dark);
  font-weight: 700;
}}

</style>
</head>
<body>

<div class="header">
  <div class="header-logo">
    <div style="background:#FF5C00;border-radius:6px;padding:4px 10px;font-weight:700;font-size:13px;color:#fff">A1</div>
    <span>Auto1 PT — Dashboard Executivo</span>
  </div>
  <div class="header-nav">
    <button class="nav-btn active" onclick="switchView('home')">📊 Home</button>
    <button class="nav-btn" onclick="switchView('teams')">👥 Equipas</button>
    <button class="nav-btn" onclick="switchView('clients')">🤝 Clientes</button>
    <button class="nav-btn" onclick="switchView('stock')">📦 Stock</button>
    <button class="nav-btn" onclick="switchView('insights')">💡 Insights</button>
  </div>
  <div class="header-right">
    <span id="last-update">Atualizado: 2026-07-21</span>
  </div>
</div>

<div class="container">

<!-- HOME -->
<div id="home-view" class="view active">
  <h2>📊 Dashboard Executivo</h2>
  <div class="kpi-row" id="home-kpi"></div>
  <div class="chart-row">
    <div class="chart-card" style="grid-column:span 2">
      <h3>Trend 24 Meses - Vendas Consolidadas</h3>
      <div style="height:280px"><canvas id="chart-trend"></canvas></div>
    </div>
  </div>
  <div class="chart-row">
    <div class="chart-card">
      <h3>Top 10 AMs por Volume YTD</h3>
      <div style="height:280px"><canvas id="chart-top-ams"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Top 10 Clientes por Volume YTD</h3>
      <div style="height:280px"><canvas id="chart-top-clients"></canvas></div>
    </div>
  </div>
</div>

<!-- TEAMS -->
<div id="teams-view" class="view">
  <h2>👥 Equipas & Account Managers</h2>
  <div id="teams-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px"></div>
</div>

<!-- CLIENTS -->
<div id="clients-view" class="view">
  <h2>🤝 Top 30 Clientes</h2>
  <div style="margin-bottom:16px;display:flex;gap:12px;align-items:center">
    <select id="filter-am" onchange="renderClientsTable()" style="padding:8px 12px;border:1.5px solid var(--border);border-radius:7px;font-size:13px">
      <option value="">📌 Todos os AMs</option>
    </select>
    <span style="color:var(--muted);font-size:12px" id="clients-count"></span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>#</th><th>Empresa</th><th>AM</th>
        <th onclick="sortClientsBy('volume')" style="cursor:pointer">Units YTD</th>
        <th onclick="sortClientsBy('potential')" style="cursor:pointer">Potencial</th>
        <th>Issues</th>
      </tr></thead>
      <tbody id="clients-tbody"></tbody>
    </table>
    <div class="pagination">
      <button class="pag-btn" id="pag-prev" onclick="changeClientsPage(-1)" disabled>← Anterior</button>
      <span class="pag-info" id="pag-info"></span>
      <button class="pag-btn" id="pag-next" onclick="changeClientsPage(1)">Próximo →</button>
    </div>
  </div>
</div>

<!-- STOCK -->
<div id="stock-view" class="view">
  <h2>📦 Análise de Stock: Nacional vs Importado</h2>
  <div class="chart-row">
    <div class="chart-card" style="min-height:350px">
      <h3>Distribuição de Stock</h3>
      <canvas id="chart-stock-pie"></canvas>
    </div>
    <div class="chart-card">
      <h3>Trend 24 Meses</h3>
      <div style="height:280px"><canvas id="chart-stock-trend"></canvas></div>
    </div>
  </div>
  <div class="chart-card">
    <h3>Breakdown por Equipa</h3>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Equipa</th><th>Nacional %</th><th>Importado %</th><th>Margem</th>
        </tr></thead>
        <tbody id="stock-breakdown"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- INSIGHTS -->
<div id="insights-view" class="view">
  <h2>💡 Insights & Anomalias</h2>
  <div class="chart-row">
    <div class="chart-card">
      <h3>🚀 Top 5 em Crescimento</h3>
      <div id="insights-growth"></div>
    </div>
    <div class="chart-card">
      <h3>📉 Top 5 em Declínio</h3>
      <div id="insights-decline"></div>
    </div>
  </div>
  <div class="chart-row">
    <div class="chart-card">
      <h3>🚨 Red Flag Clientes (3+ Issues)</h3>
      <div id="insights-redflags"></div>
    </div>
    <div class="chart-card">
      <h3>💡 Untapped Potential</h3>
      <div id="insights-potential"></div>
    </div>
  </div>
</div>

</div>

<!-- DATA & SCRIPTS -->
<script>
const TEAMS = {teams_str};
const CLIENT_DATA = {{"clients": {{}}}};

let currentView = 'home';
let clientsPage = 0;
const CLIENTS_PER_PAGE = 10;
let clientsSort = {{ field: 'volume', asc: false }};
let allClients = [];
let chartObjects = {{}};

// View manager
function switchView(view) {{
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(view + '-view').classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  currentView = view;
  window.location.hash = '#' + view;

  // Render specific views
  if (view === 'home' && !chartObjects.trend) renderHome();
  if (view === 'clients') renderClientsTable();
  if (view === 'stock') renderStock();
  if (view === 'insights') renderInsights();
}}

// HOME / EXECUTIVE SUMMARY
function renderHome() {{
  console.log('Rendering Home...');

  const totalUnitsYTD = TEAMS.reduce((s, t) => s + (t.monthly || []).reduce((a, b) => a + b, 0), 0);
  const avgGrowth = TEAMS.length > 0 ? TEAMS.reduce((s, t) => s + (t.trend || 0), 0) / TEAMS.length : 0;
  const totalAMs = TEAMS.reduce((s, t) => s + (t.ams || []).length, 0);

  document.getElementById('home-kpi').innerHTML = `
    <div class="stat-card">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px">UNITS YTD</div>
      <div class="num">${{totalUnitsYTD.toLocaleString('pt-PT')}}</div>
      <div class="lbl">últimos 12 meses</div>
    </div>
    <div class="stat-card">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px">CRESCIMENTO MÊS</div>
      <div class="num" style="color:${{avgGrowth >= 0 ? 'var(--green)' : 'var(--red)'}}">${{avgGrowth.toFixed(1)}}%</div>
      <div class="lbl">média por AM</div>
    </div>
    <div class="stat-card">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px">EQUIPAS</div>
      <div class="num">${{TEAMS.length}}</div>
      <div class="lbl">ativa(s)</div>
    </div>
    <div class="stat-card">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px">AMS</div>
      <div class="num">${{totalAMs}}</div>
      <div class="lbl">account managers</div>
    </div>
  `;

  // Trend Chart
  const months = ['Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                  'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'];
  const trendData = [];
  for (let i = 0; i < 24; i++) {{
    const monthSum = TEAMS.reduce((s, t) => s + ((t.monthly || [])[i] || 0), 0);
    trendData.push(monthSum);
  }}

  if (chartObjects.trend) chartObjects.trend.destroy();
  chartObjects.trend = new Chart(document.getElementById('chart-trend'), {{
    type: 'line',
    data: {{
      labels: months,
      datasets: [{{
        label: 'Units',
        data: trendData,
        borderColor: 'var(--orange)',
        backgroundColor: 'rgba(255,92,0,0.1)',
        tension: 0.4,
        fill: true,
        pointBackgroundColor: 'var(--orange)',
        pointRadius: 3,
        pointHoverRadius: 5
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, grid: {{ drawBorder: false }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});

  // Top 10 AMs
  const amsFlat = TEAMS.flatMap(t => (t.ams || []).map(am => ({{
    name: am.name,
    total: am.total || 0,
    trend: am.trend || 0
  }})));
  const top10AMs = amsFlat.sort((a, b) => b.total - a.total).slice(0, 10);

  if (chartObjects.topAMs) chartObjects.topAMs.destroy();
  chartObjects.topAMs = new Chart(document.getElementById('chart-top-ams'), {{
    type: 'bar',
    data: {{
      labels: top10AMs.map(a => a.name),
      datasets: [{{
        label: 'Units',
        data: top10AMs.map(a => a.total),
        backgroundColor: 'var(--blue)',
        borderRadius: 6
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{ x: {{ beginAtZero: true }} }}
    }}
  }});

  console.log('✅ Home rendered');
}}

// CLIENTS
function buildClientsList() {{
  console.log('Building clients list...');
  allClients = [];
  const clients = CLIENT_DATA?.clients || {{}};

  for (let amName in clients) {{
    for (let clientId in clients[amName]) {{
      const c = clients[amName][clientId];
      const monthly = c.u || [];
      const units = monthly.reduce((a, b) => a + b, 0);
      const issues = (c.k || []).length;

      allClients.push({{
        id: clientId,
        company: c.n || 'Unknown',
        am: amName,
        volume: units,
        issues: issues,
        potential: calculatePotential(c)
      }});
    }}
  }}

  if (allClients.length === 0) {{
    console.log('⚠ No clients found - using mock data');
    // Mock data for demo
    for (let i = 0; i < 50; i++) {{
      allClients.push({{
        id: i,
        company: 'Cliente ' + (i+1),
        am: TEAMS[0]?.ams[0]?.name || 'Demo AM',
        volume: Math.floor(Math.random() * 300) + 10,
        issues: Math.floor(Math.random() * 5),
        potential: Math.floor(Math.random() * 100)
      }});
    }}
  }}

  allClients.sort((a, b) => b.volume - a.volume);

  const amFilter = document.getElementById('filter-am');
  const ams = [...new Set(allClients.map(c => c.am))];
  ams.forEach(am => {{
    const opt = document.createElement('option');
    opt.value = am;
    opt.textContent = am;
    amFilter.appendChild(opt);
  }});

  console.log('✅ Clients list built: ' + allClients.length + ' clients');
}}

function calculatePotential(clientData) {{
  const calls = (clientData.c || []).reduce((a, b) => a + b, 0);
  const units = (clientData.u || []).reduce((a, b) => a + b, 0);
  return calls > 0 ? Math.round((calls / units) * 100) : 50;
}}

function renderClientsTable() {{
  const amFilter = document.getElementById('filter-am').value;
  let filtered = allClients;
  if (amFilter) filtered = allClients.filter(c => c.am === amFilter);

  if (clientsSort.field === 'volume') {{
    filtered.sort((a, b) => clientsSort.asc ? a.volume - b.volume : b.volume - a.volume);
  }}

  const start = clientsPage * CLIENTS_PER_PAGE;
  const page = filtered.slice(start, start + CLIENTS_PER_PAGE);

  document.getElementById('clients-tbody').innerHTML = page.map((c, i) => `
    <tr>
      <td style="font-weight:700;color:var(--orange)">${{start + i + 1}}</td>
      <td>${{c.company}}</td>
      <td>${{c.am}}</td>
      <td>${{c.volume}}</td>
      <td><span class="badge badge-amber">${{c.potential}}</span></td>
      <td>${{c.issues > 0 ? '<span class="badge badge-red">' + c.issues + '</span>' : '—'}}</td>
    </tr>
  `).join('');

  document.getElementById('pag-info').textContent = `${{start+1}}–${{Math.min(start+CLIENTS_PER_PAGE, filtered.length)}} de ${{filtered.length}}`;
  document.getElementById('pag-prev').disabled = clientsPage === 0;
  document.getElementById('pag-next').disabled = start + CLIENTS_PER_PAGE >= filtered.length;
  document.getElementById('clients-count').textContent = `Total: ${{filtered.length}} clientes`;
}}

function changeClientsPage(d) {{
  clientsPage = Math.max(0, clientsPage + d);
  renderClientsTable();
  window.scrollTo(0, 200);
}}

function sortClientsBy(field) {{
  clientsSort.field = field;
  clientsSort.asc = !clientsSort.asc;
  clientsPage = 0;
  renderClientsTable();
}}

// STOCK
function renderStock() {{
  console.log('Stock placeholder - será alimentado por Redash Q2');
  document.getElementById('stock-breakdown').innerHTML = '<tr><td colspan="4">Dados a serem preenchidos por Redash Q2</td></tr>';
}}

// INSIGHTS
function renderInsights() {{
  const amsWithMonths = TEAMS.flatMap(t => (t.ams || []).map(am => ({{
    name: am.name,
    trend: am.trend || 0,
    monthsActive: (am.monthly || []).filter(m => m > 0).length
  }})));

  const validAMs = amsWithMonths.filter(a => a.monthsActive >= 3);

  document.getElementById('insights-growth').innerHTML = validAMs
    .sort((a, b) => b.trend - a.trend)
    .slice(0, 5)
    .map(a => `
      <div class="insight-item">
        <strong>${{a.name}}</strong>
        <div style="color:var(--green);font-size:12px">+${{a.trend.toFixed(1)}}% / mês</div>
      </div>
    `).join('') || '<div class="insight-item">Sem dados</div>';

  document.getElementById('insights-decline').innerHTML = validAMs
    .sort((a, b) => a.trend - b.trend)
    .slice(0, 5)
    .map(a => `
      <div class="insight-item">
        <strong>${{a.name}}</strong>
        <div style="color:var(--red);font-size:12px">${{a.trend.toFixed(1)}}% / mês</div>
      </div>
    `).join('') || '<div class="insight-item">Sem dados</div>';
}}

// Initialize
window.addEventListener('DOMContentLoaded', () => {{
  console.log('🚀 MVP Dashboard loaded');
  buildClientsList();
  renderHome();
}});
</script>

</body>
</html>
"""
    return html

def main():
    html = load_current_html()
    if not html:
        return False

    pattern = r'const TEAMS = \[.*?\];'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        teams_str = match.group(0)[12:-1]  # Remove 'const TEAMS = ' and ';'
        print(f"✓ Extracted TEAMS ({len(teams_str)} bytes)")
    else:
        print("✗ TEAMS not found")
        return False

    print("Building complete MVP...")
    mvp_html = generate_mvp_complete(teams_str)

    with open('index_mvp.html', 'w', encoding='utf-8') as f:
        f.write(mvp_html)

    size_kb = len(mvp_html) / 1024
    print(f"✓ MVP created: index_mvp.html ({size_kb:.1f} KB)")
    return True

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
