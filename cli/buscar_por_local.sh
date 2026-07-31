#!/usr/bin/env bash
# ==============================================================================
# Script para realizar busca por local (cidade/estado) - POST /api/v1/buscar/por-local
# Uso: ./cli/buscar_por_local.sh ORIGEM_TIPO ORIGEM_VALOR DESTINO_TIPO DESTINO_VALOR DATA_PARTIDA [DATA_RETORNO] [BASE_URL] [TOKEN]
# Exemplo: ./cli/buscar_por_local.sh cidade Vitória cidade "São Paulo" 2026-08-10
# ==============================================================================

set -euo pipefail

ORIGEM_TIPO="${1:-cidade}"
ORIGEM_VALOR="${2:-Vitória}"
DESTINO_TIPO="${3:-cidade}"
DESTINO_VALOR="${4:-São Paulo}"
DATA_PARTIDA="${5:-2026-08-10}"
DATA_RETORNO="${6:-}"
BASE_URL="${7:-http://127.0.0.1:12000}"
TOKEN="${8:-${FLIGHTS_API_INTERNAL_TOKEN:-}}"

URL="${BASE_URL}/api/v1/buscar/por-local"

echo "=========================================================="
echo " 🌐 Busca por Local (POST /api/v1/buscar/por-local)"
echo " Origem:       $ORIGEM_TIPO = $ORIGEM_VALOR"
echo " Destino:      $DESTINO_TIPO = $DESTINO_VALOR"
echo " Data Partida: $DATA_PARTIDA"
echo " Data Retorno: ${DATA_RETORNO:-[Só Ida]}"
echo " Target API:   $URL"
echo "=========================================================="

PAYLOAD=$(cat <<EOF
{
  "origem_tipo": "${ORIGEM_TIPO}",
  "origem_valor": "${ORIGEM_VALOR}",
  "destino_tipo": "${DESTINO_TIPO}",
  "destino_valor": "${DESTINO_VALOR}",
  "data_partida": "${DATA_PARTIDA}"$(if [ -n "$DATA_RETORNO" ]; then echo ", \"data_retorno\": \"${DATA_RETORNO}\""; fi)
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
