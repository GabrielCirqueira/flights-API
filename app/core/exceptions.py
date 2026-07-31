import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("flights_api")


async def tratar_excecao_http(request: Request, exc: HTTPException) -> JSONResponse:
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
