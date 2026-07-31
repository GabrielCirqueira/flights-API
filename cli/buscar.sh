#!/usr/bin/env bash
# ==============================================================================
# Script para realizar busca pontual por data exata (/api/v1/buscar)
# Uso: ./cli/buscar.sh [ORIGEM] [DESTINO] [DATA_PARTIDA] [DATA_RETORNO] [BASE_URL] [TOKEN]
# Exemplo: ./cli/buscar.sh VIX GRU 2026-08-10 2026-08-15 http://127.0.0.1:12000
# ==============================================================================

set -euo pipefail

ORIGEM="${1:-VIX}"
DESTINO="${2:-GRU}"
DATA_PARTIDA="${3:-2026-08-10}"
DATA_RETORNO="${4:-}"
BASE_URL="${5:-http://127.0.0.1:12000}"
TOKEN="${6:-${FLIGHTS_API_INTERNAL_TOKEN:-}}"

URL="${BASE_URL}/api/v1/buscar"

echo "=========================================================="
echo " ✈️  Busca Pontual de Voos (POST /api/v1/buscar)"
echo " Origem:       $ORIGEM"
echo " Destino:      $DESTINO"
echo " Data Partida: $DATA_PARTIDA"
echo " Data Retorno: ${DATA_RETORNO:-[Só Ida]}"
echo " Target API:   $URL"
echo "=========================================================="

PAYLOAD=$(cat <<EOF
{
  "origem": "${ORIGEM}",
  "destino": "${DESTINO}",
  "data_partida": "${DATA_PARTIDA}"
  $( [ -n "$DATA_RETORNO" ] && echo ", \"data_retorno\": \"${DATA_RETORNO}\"" )
}
EOF
)

CABECALHOS=(-H "Content-Type: application/json")
if [ -n "$TOKEN" ]; then
  CABECALHOS+=(-H "X-Internal-Token: ${TOKEN}")
fi

RESPOSTA=$(curl -s -w "\n%{http_code}" "${CABECALHOS[@]}" -X POST -d "$PAYLOAD" "$URL" || echo -e "\n000")
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
