#!/usr/bin/env bash
# ==============================================================================
# Script de verificação de saúde da Flights API
# Uso: ./cli/saude.sh [URL]
# Exemplo: ./cli/saude.sh http://127.0.0.1:12000
# ==============================================================================

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:12000}"
SAUDE_URL="${BASE_URL}/saude"

echo "[CLI] Verificando status do serviço em: ${SAUDE_URL}..."

RESPOSTA=$(curl -s -w "\n%{http_code}" "${SAUDE_URL}" || echo -e "\n000")
CORPO=$(echo "$RESPOSTA" | head -n 1)
STATUS=$(echo "$RESPOSTA" | tail -n 1)

if [ "$STATUS" -eq 200 ]; then
  echo "✅ Serviço SAUDÁVEL! (HTTP status $STATUS)"
  if command -v jq &> /dev/null; then
    echo "$CORPO" | jq '.'
  else
    echo "$CORPO"
  fi
  exit 0
else
  echo "❌ Serviço INDISPONÍVEL ou Inacessível! (HTTP status $STATUS)"
  echo "Resposta: $CORPO"
  exit 1
fi
