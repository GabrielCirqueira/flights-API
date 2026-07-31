#!/usr/bin/env bash
# ==============================================================================
# Script para realizar busca por janela de datas (/api/v1/buscar/janela)
# Uso: ./cli/buscar_janela.sh [ORIGEM] [DESTINO] [DATA_INICIO] [DATA_FIM] [EXPANDIR_TOP] [BASE_URL] [TOKEN]
# Exemplo: ./cli/buscar_janela.sh VIX GRU 2026-08-02 2026-08-08 1 http://127.0.0.1:12000
# ==============================================================================

set -euo pipefail

ORIGEM="${1:-VIX}"
DESTINO="${2:-GRU}"
DATA_INICIO="${3:-2026-08-02}"
DATA_FIM="${4:-2026-08-08}"
EXPANDIR_TOP="${5:-1}"
BASE_URL="${6:-http://127.0.0.1:12000}"
TOKEN="${7:-${FLIGHTS_API_INTERNAL_TOKEN:-}}"

URL="${BASE_URL}/api/v1/buscar/janela"

echo "=========================================================="
echo " 📅 Busca Por Janela de Datas (POST /api/v1/buscar/janela)"
echo " Origem:       $ORIGEM"
echo " Destino:      $DESTINO"
echo " Intervalo:    $DATA_INICIO até $DATA_FIM"
echo " Expandir Top: $EXPANDIR_TOP"
echo " Target API:   $URL"
echo "=========================================================="

PAYLOAD=$(cat <<EOF
{
  "origem": "${ORIGEM}",
  "destino": "${DESTINO}",
  "data_inicio": "${DATA_INICIO}",
  "data_fim": "${DATA_FIM}",
  "expandir_top": ${EXPANDIR_TOP}
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
