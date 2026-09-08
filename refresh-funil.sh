#!/bin/bash
# Regenera data-funil.json com o funil de conversão REAL por AM e período,
# a partir do Redash (data source 89, wkda_dm_es).
#
# A API key NUNCA fica no ficheiro. Passa-a por ambiente:
#   REDASH_API_KEY=xxxx ./refresh-funil.sh
#
# Requisitos: curl, python3
set -euo pipefail

API_KEY="${REDASH_API_KEY:?Define REDASH_API_KEY no ambiente antes de correr}"
U="https://dash.prod.bi.auto1.team/api"
DS=89

read -r -d '' SQL <<'SQLEOF' || true
WITH am_pt AS (
  SELECT id, firstname||' '||name AS full_name
  FROM wkda_dm_es.users
  WHERE main_country='PT' AND position_id IN (192,97,911,5,154) AND status=1),
periods AS (
  SELECT 'WTD' period, DATE_TRUNC('week', CURRENT_DATE) s UNION ALL
  SELECT 'MTD', DATE_TRUNC('month', CURRENT_DATE) UNION ALL
  SELECT 'YTD', DATE_TRUNC('year', CURRENT_DATE) UNION ALL
  SELECT '12M', (CURRENT_DATE - INTERVAL '12 months') UNION ALL
  SELECT '24M', (CURRENT_DATE - INTERVAL '24 months')),
calls_raw AS (
  SELECT a.full_name am_name, fmc.merchant_id mid, fmc.start_datetime_berlin_timezone::date d
  FROM wkda_dm_es.fact_merchant_calls fmc JOIN am_pt a ON a.id=fmc.calling_agent_id
  WHERE fmc.is_successful_call=true AND fmc.start_datetime_berlin_timezone >= CURRENT_DATE - INTERVAL '24 months'),
v_last AS (SELECT merchant_id mid, MAX(created_at::date) md FROM wkda_dm_es.car_views
  WHERE created_at >= CURRENT_DATE - INTERVAL '24 months' GROUP BY merchant_id),
w_last AS (SELECT mu.merchant_id mid, MAX(mwc.created_on::date) md FROM wkda_dm_es.mp_watched_cars mwc
  JOIN wkda_dm_es.mp_users mu ON mu.user_id=mwc.mp_user_id
  WHERE mwc.created_on >= CURRENT_DATE - INTERVAL '24 months' GROUP BY mu.merchant_id),
b_last AS (SELECT mu.merchant_id mid, MAX(mlo.created_datetime::date) md FROM wkda_dm_es.mp_live_market_offers mlo
  JOIN wkda_dm_es.mp_users mu ON mu.user_id=mlo.user_id
  WHERE mlo.created_datetime >= CURRENT_DATE - INTERVAL '24 months' GROUP BY mu.merchant_id),
p_raw AS (SELECT a.full_name am_name, cs.buyer_id mid, cs.b2b_deal_datetime::date d
  FROM wkda_dm_es.car_sales cs JOIN wkda_dm_es.car_leads cl ON cl.id=cs.id
  JOIN am_pt a ON a.id=cs.assigned_agent_id
  WHERE cl.status_id IN (114,14) AND cs.b2b_deal_datetime >= CURRENT_DATE - INTERVAL '24 months'),
cap AS (SELECT p.period, c.am_name, c.mid, COUNT(*) calls_cnt
  FROM calls_raw c JOIN periods p ON c.d >= p.s GROUP BY p.period, c.am_name, c.mid),
pap AS (SELECT p.period, pr.am_name, pr.mid, COUNT(*) units
  FROM p_raw pr JOIN periods p ON pr.d >= p.s GROUP BY p.period, pr.am_name, pr.mid)
SELECT cap.period, cap.am_name,
 SUM(cap.calls_cnt) calls_success,
 COUNT(DISTINCT cap.mid) dealers_called,
 COUNT(DISTINCT CASE WHEN vl.md >= pr.s THEN cap.mid END) dealers_views,
 COUNT(DISTINCT CASE WHEN wl.md >= pr.s THEN cap.mid END) dealers_watchlist,
 COUNT(DISTINCT CASE WHEN bl.md >= pr.s THEN cap.mid END) dealers_bids,
 COUNT(DISTINCT CASE WHEN pap.mid IS NOT NULL THEN cap.mid END) dealers_purchase,
 COALESCE(SUM(pap.units),0) units_sold
FROM cap
JOIN periods pr ON pr.period=cap.period
LEFT JOIN v_last vl ON vl.mid=cap.mid
LEFT JOIN w_last wl ON wl.mid=cap.mid
LEFT JOIN b_last bl ON bl.mid=cap.mid
LEFT JOIN pap ON pap.period=cap.period AND pap.am_name=cap.am_name AND pap.mid=cap.mid
GROUP BY cap.period, cap.am_name
SQLEOF

echo "🔄 A executar query do funil no Redash…"
JOB=$(curl -s -H "Authorization: Key $API_KEY" -H "Content-Type: application/json" \
  -X POST "$U/query_results" \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"query":sys.argv[1],"data_source_id":int(sys.argv[2]),"max_age":0}))' "$SQL" "$DS")")
JID=$(echo "$JOB" | python3 -c "import sys,json;print(json.load(sys.stdin).get('job',{}).get('id',''))")
[ -z "$JID" ] && { echo "❌ Sem job: $JOB"; exit 1; }

QRID=""
for i in $(seq 1 60); do
  sleep 3
  ST=$(curl -s -H "Authorization: Key $API_KEY" "$U/jobs/$JID")
  STATUS=$(echo "$ST" | python3 -c "import sys,json;print(json.load(sys.stdin).get('job',{}).get('status',''))")
  QRID=$(echo "$ST" | python3 -c "import sys,json;print(json.load(sys.stdin).get('job',{}).get('query_result_id') or '')")
  [ "$STATUS" = "3" ] && [ -n "$QRID" ] && break
  [ "$STATUS" = "4" ] && { echo "❌ Query falhou"; echo "$ST" | python3 -c "import sys,json;print(json.load(sys.stdin).get('job',{}).get('error','')[:500])"; exit 1; }
done
[ -z "$QRID" ] && { echo "❌ Timeout"; exit 1; }

echo "✅ Resultado pronto (qrid=$QRID). A gerar data-funil.json…"
curl -s -H "Authorization: Key $API_KEY" "$U/query_results/$QRID.json" | python3 -c '
import json,sys
rows = json.load(sys.stdin)["query_result"]["data"]["rows"]
ams = {}
for r in rows:
    a = ams.setdefault(r["am_name"], {})
    a[r["period"]] = {"calls":r["calls_success"],"called":r["dealers_called"],"views":r["dealers_views"],
                      "watchlist":r["dealers_watchlist"],"bids":r["dealers_bids"],
                      "purchase":r["dealers_purchase"],"units":r["units_sold"]}
out = {"_fonte":"Redash data source 89 (wkda_dm_es). Funil real por AM e periodo. Cohort = dealers com chamada com sucesso do AM no periodo; etapas = dealers unicos dessa cohort que viram carros / watchlist / bid / compraram, na janela. calls=chamadas com sucesso, units=unidades vendidas.",
       "periods":["WTD","MTD","YTD","12M","24M"], "ams":ams}
json.dump(out, open("data-funil.json","w"), ensure_ascii=False, indent=0)
print("   AMs:", len(ams))
'
echo "💾 Feito. Faz commit e push:"
echo "   git add data-funil.json && git commit -m 'chore: refresh funil real' && git push origin main"
