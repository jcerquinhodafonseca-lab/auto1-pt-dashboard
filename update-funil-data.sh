#!/bin/bash
# Script para atualizar dados do Funil de Conversão do Redash

API_KEY="Cbw7xonVpyBrDWTf09oLhFvCwdTS5EYv32iK7avK"
REDASH_URL="https://dash.prod.bi.auto1.team/api"

echo "🔄 Atualizando dados do Funil..."

# Query 138700 - Funil Geral
echo "  → Executando Query 138700 (Funil Geral)..."
curl -s -X POST -H "Authorization: Key $API_KEY" \
  "$REDASH_URL/queries/138700/results" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null

sleep 15  # Aguardar execução

# Query 138684 - Funil Individual
echo "  → Executando Query 138684 (Funil Individual)..."
curl -s -X POST -H "Authorization: Key $API_KEY" \
  "$REDASH_URL/queries/138684/results" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null

sleep 15

# Fetch resultados
GERAL=$(curl -s -H "Authorization: Key $API_KEY" \
  "$REDASH_URL/queries/138700/results.json" | jq '.query_result.data.rows[0]')

INDIVIDUAL=$(curl -s -H "Authorization: Key $API_KEY" \
  "$REDASH_URL/queries/138684/results.json" | jq '.query_result.data.rows[0:100]')

# Guardar em JSON
cat > data-funil.json << EOF
{
  "funil_geral": $GERAL,
  "funil_individual": $INDIVIDUAL
}
EOF

echo "✅ Dados atualizados em data-funil.json!"
echo "💾 Agora faz commit e push:"
echo "   git add data-funil.json"
echo "   git commit -m 'chore: Update funil data from Redash'"
echo "   git push origin main"
