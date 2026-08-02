.PHONY: help install dev-install run dev stop lint format docker-build docker-run clean cli-saude cli-buscar cli-buscar-janela

VENV = .venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
UVICORN = $(VENV)/bin/uvicorn
RUFF = $(VENV)/bin/ruff

PORT ?= 12000
HOST ?= 0.0.0.0

help:
	@echo "======================================================================"
	@echo "              VOO BARATO - FLIGHTS API - MAKEFILE                     "
	@echo "======================================================================"
	@echo "  make dev                Cria venv, instala dependências e sobe a API em dev"
	@echo "  make stop               Encerra uvicorn na porta $(PORT)"
	@echo "  make run                Cria venv, instala prod e sobe a API em produção"
	@echo "  make lint               Executa verificação de linting com Ruff"
	@echo "  make format             Formata o código-fonte com Ruff"
	@echo "  make docker-build       Constrói a imagem Docker local"
	@echo "  make docker-run         Executa o container Docker na porta $(PORT)"
	@echo "  make clean              Remove venv e caches de Python"
	@echo "======================================================================"

$(VENV):
	python3 -m venv $(VENV)

install: $(VENV)
	$(PIP) install -r requirements.txt

dev-install: $(VENV)
	$(PIP) install -r requirements.txt -r requirements-dev.txt

run: install stop
	$(UVICORN) app.main:app --host $(HOST) --port $(PORT) --workers 2

stop:
	@pgrep -f '[.]venv/bin/[u]vicorn app.main:app' 2>/dev/null | xargs -r kill 2>/dev/null || true
	@sleep 0.5

dev: dev-install stop
	$(UVICORN) app.main:app --host $(HOST) --port $(PORT) --reload

lint: dev-install
	$(RUFF) check app/

format: dev-install
	$(RUFF) format app/

docker-build:
	docker build -t voobarato-flights-api .

docker-run:
	docker run --rm -p $(PORT):$(PORT) --env-file .env voobarato-flights-api

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .ruff_cache $(VENV)

cli-saude:
	./cli/saude.sh

cli-buscar:
	./cli/buscar.sh

cli-buscar-janela:
	./cli/buscar_janela.sh

cli-aeroportos:
	./cli/aeroportos.sh

cli-buscar-por-local:
	./cli/buscar_por_local.sh
