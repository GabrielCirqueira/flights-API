import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import configuracoes

_PREFIXOS_ROTAS_PUBLICAS = (
    "/api/v1/aeroportos",
    "/api/v1/cidades",
    "/api/v1/cities",
)


def _rota_publica(path: str) -> bool:
    if path == "/saude":
        return True
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _PREFIXOS_ROTAS_PUBLICAS)


async def rastreamento_e_autenticacao(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    if configuracoes.TOKEN_INTERNO and not _rota_publica(request.url.path):
        token = (request.headers.get("X-Internal-Token") or "").strip()
        if token != configuracoes.TOKEN_INTERNO:
            resposta = JSONResponse(status_code=401, content={"error": "nao_autorizado"})
            resposta.headers["X-Request-ID"] = request_id
            return resposta

    resposta = await call_next(request)
    resposta.headers["X-Request-ID"] = request_id
    return resposta
