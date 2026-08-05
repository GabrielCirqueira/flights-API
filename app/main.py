import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import configuracoes
from app.core.exceptions import tratar_excecao_http
from app.core.middleware import rastreamento_e_autenticacao
from app.core.upstream import configurar_upstream
from app.routers import aeroportos, buscar, cidades, saude

logging.basicConfig(level=logging.INFO)
configurar_upstream()

app = FastAPI(
    title=configuracoes.NOME_SERVICO,
    version=configuracoes.VERSAO_SERVICO,
    description="Microsserviço de busca de voos baseado no pacote fli "
    "(acesso direto à API interna do Google Flights, sem HTML parsing).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(rastreamento_e_autenticacao)
app.exception_handler(HTTPException)(tratar_excecao_http)

app.include_router(saude.roteador)
app.include_router(buscar.roteador)
app.include_router(aeroportos.roteador)
app.include_router(cidades.roteador)
