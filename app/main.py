import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import configuracoes
from app.routers import aeroportos, buscar, saude

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flights_api")

app = FastAPI(
    title=configuracoes.NOME_SERVICO,
    version=configuracoes.VERSAO_SERVICO,
    description="Microsserviço de busca de voos baseado no pacote fli "
    "(acesso direto à API interna do Google Flights, sem HTML parsing).",
)

@app.middleware("http")
async def gerenciar_rastreamento_e_autenticacao(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    if configuracoes.TOKEN_INTERNO and request.url.path != "/saude":
        token = request.headers.get("X-Internal-Token")
        if token != configuracoes.TOKEN_INTERNO:
            resposta = JSONResponse(status_code=401, content={"error": "nao_autorizado"})
            resposta.headers["X-Request-ID"] = request_id
            return resposta

    resposta = await call_next(request)
    resposta.headers["X-Request-ID"] = request_id
    return resposta

@app.exception_handler(HTTPException)
async def tratar_excecao_http(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "sem-id")
    logger.warning(
        "excecao_http req_id=%s path=%s status=%s detail=%s",
        request_id,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    resposta = JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    resposta.headers["X-Request-ID"] = request_id
    return resposta

app.include_router(saude.roteador)
app.include_router(buscar.roteador)
app.include_router(aeroportos.roteador)