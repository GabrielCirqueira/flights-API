from fastapi import APIRouter

from app.core.config import configuracoes

roteador = APIRouter(tags=["saude"])

@roteador.get("/saude")
def saude() -> dict:
    return {
        "status": "ok",
        "servico": configuracoes.NOME_SERVICO,
        "versao": configuracoes.VERSAO_SERVICO,
    }
