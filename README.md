# ✈️ voobarato-flights-api

Microsserviço de busca de voos baseado no pacote [`fli`](https://github.com/punitarani/fli) (`pip install flights`) -- acesso direto à API interna do Google Flights via requisições RPC com TLS fingerprinting, sem parsing de HTML e sem navegadores headless.

---

## ⚡ TL;DR — Como rodar em um novo sistema

Escolha **apenas 1 das opções abaixo** dependendo de como você quer rodar:

### 🐋 Opção A: Em Produção / Servidor (Usando Docker — RECOMENDADO)
Não precisa instalar Python nem gerenciar ambientes. Rodar apenas:
```bash
docker-compose up -d --build
```
*A API já estará rodando na porta **12000** (ou na porta definida no seu `.env`).*

---

### 💻 Opção B: No seu computador (Desenvolvimento Local)
Basta ter o `python3` instalado e rodar **1 único comando**:
```bash
make dev
```
*O `Makefile` cria automaticamente o ambiente virtual `.venv`, instala todas as dependências necessárias e já inicia o servidor na porta **12000** com hot-reload, escutando em **0.0.0.0** (acessível pelos containers Docker do Voo-Barato). Para só localhost: `make dev HOST=127.0.0.1`.*

---

## 🛠️ Ferramentas de Linha de Comando (CLI)

O repositório possui scripts executáveis em português na pasta [`cli/`](file:///home/gabriel/dev/pessoal/voo-flights/cli/) para facilitar interações e automações:

```bash
# 1. Healthcheck rápido
./cli/saude.sh http://127.0.0.1:12000

# 2. Realizar busca pontual por data exata
./cli/buscar.sh VIX GRU 2026-08-10 2026-08-15

# 3. Realizar busca por janela de datas
./cli/buscar_janela.sh VIX GRU 2026-08-02 2026-08-08 1

# 4. Smoke test end-to-end contra servidor ativo
./cli/testar_ao_vivo.sh http://127.0.0.1:12000
```

---

## 📋 Para que serve cada comando no `Makefile`? (Resumo)

O `Makefile` é apenas um **atalho opcional**. Você não precisa usar todos os comandos!

| Comando | Quando usar? | O que ele faz? |
| :--- | :--- | :--- |
| `make dev` | No dia a dia local | Cria venv, instala dependências e sobe a API (`--reload`) |
| `make lint` | Para verificar código | Roda verificação de código (`ruff`) |
| `make format` | Formatar código | Aplica formatação automática (`ruff format`) |
| `make docker-build` | Para criar a imagem Docker | Roda `docker build` |
| `make run` | Em servidor sem Docker | Sobe a API em produção com 2 workers |
| `make cli-saude` | Testar o /saude | Executa `./cli/saude.sh` |
| `make cli-buscar` | Testar /api/v1/buscar | Executa `./cli/buscar.sh` |
| `make cli-buscar-janela` | Testar /api/v1/buscar/janela | Executa `./cli/buscar_janela.sh` |

---

## 🧪 Qualidade de Código

```bash
make lint
make format
```

---

## 📚 Documentação Técnica Detalhada

* **[Documentação Técnica (`docs/DOCUMENTACAO_TECNICA.md`)](./docs/DOCUMENTACAO_TECNICA.md)**: Estrutura de pastas, arquivos e funcionalidade geral.
* **[Especificação da API REST (`docs/API.md`)](./docs/API.md)**: Endpoints, payloads, modelos de oferta e exemplos curl.
* **[Arquitetura e Decisões de Design (`docs/ARCHITECTURE.md`)](./docs/ARCHITECTURE.md)**: Visão geral, fluxo de dados e decisões de design.

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](file:///home/gabriel/dev/pessoal/voo-flights/LICENSE) para mais detalhes.
