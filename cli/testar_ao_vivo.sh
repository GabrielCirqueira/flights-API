#!/usr/bin/env bash
# ==============================================================================
# Script de Smoke Test End-to-End para validação rápida da API em execução
# Uso: ./cli/testar_ao_vivo.sh [BASE_URL]
# ==============================================================================

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:12000}"

echo "======================================================================"
echo " 🚀 INICIANDO SMOKE TESTS AO VIVO CONTRA ${BASE_URL}"
echo "======================================================================"

# 1. Teste do Healthcheck /saude
echo -n "[1/3] Verificando /saude ... "
STATUS_SAUDE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/saude")
if [ "$STATUS_SAUDE" -eq 200 ]; then
  echo "OK (200)"
else
  echo "FALHOU (${STATUS_SAUDE})"
  exit 1
fi

# 2. Teste de Busca Pontual
echo -n "[2/3] Testando POST /api/v1/buscar ... "
PAYLOAD_BUSCA='{"origem":"VIX","destino":"GRU","data_partida":"2026-09-01"}'
STATUS_BUSCA=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$PAYLOAD_BUSCA" "${BASE_URL}/api/v1/buscar")
if [ "$STATUS_BUSCA" -eq 200 ] || [ "$STATUS_BUSCA" -eq 502 ]; then
  echo "OK (${STATUS_BUSCA})"
else
  echo "FALHOU (${STATUS_BUSCA})"
  exit 1
fi

# 3. Teste de Busca por Janela
echo -n "[3/3] Testando POST /api/v1/buscar/janela ... "
PAYLOAD_JANELA='{"origem":"VIX","destino":"GRU","data_inicio":"2026-09-01","data_fim":"2026-09-03","expandir_top":0}'
STATUS_JANELA=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$PAYLOAD_JANELA" "${BASE_URL}/api/v1/buscar/janela")
if [ "$STATUS_JANELA" -eq 200 ] || [ "$STATUS_JANELA" -eq 502 ]; then
  echo "OK (${STATUS_JANELA})"
else
  echo "FALHOU (${STATUS_JANELA})"
  exit 1
fi

echo "======================================================================"
echo " 🎉 TODOS OS SMOKE TESTS CONCLUÍDOS COM SUCESSO!"
echo "======================================================================"
