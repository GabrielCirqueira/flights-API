#!/usr/bin/env bash
# ==============================================================================
# Script para realizar busca e consulta de aeroportos (/api/v1/aeroportos)
# Uso: ./cli/aeroportos.sh [TERMO_BUSCA] [LIMITE] [BASE_URL] [TOKEN]
# Exemplo: ./cli/aeroportos.sh Guarulhos 5 http://127.0.0.1:12000
# ==============================================================================

set -euo pipefail

BUSCA="${1:-}"
LIMITE="${2:-10}"
BASE_URL="${3:-http://127.0.0.1:12000}"
TOKEN="${4:-${FLIGHTS_API_INTERNAL_TOKEN:-}}"

URL="${BASE_URL}/api/v1/aeroportos?limite=${LIMITE}"
if [ -n "$BUSCA" ]; then
  URL="${URL}&busca=${BUSCA}"
fi

echo "=========================================================="
echo " 🛫 Consulta de Aeroportos (GET /api/v1/aeroportos)"
echo " Termo Busca: ${BUSCA:-[Sem filtro]}"
echo " Limite:      $LIMITE"
echo " Target API:  $URL"
echo "=========================================================="

CABECALHOS=()
if [ -n "$TOKEN" ]; then
  CABECALHOS+=(-H "X-Internal-Token: ${TOKEN}")
fi

RESPOSTA=$(curl -s -w "\n%{http_code}" "${CABECALHOS[@]}" "$URL" || echo -e "\n000")
CORPO=$(echo "$RESPOSTA" | head -n -1)
STATUS=$(echo "$RESPOSTA" | tail -n 1)

echo "[HTTP Status: $STATUS]"

if command -v jq &> /dev/null; then
  echo "$CORPO" | jq '.'
else
  echo "$CORPO"
fi

if [ "$STATUS" -ne 200 ]; then
  exit 1
fi
