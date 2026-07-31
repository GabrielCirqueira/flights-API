from fastapi import APIRouter

from app.schemas.voos import (
    RequisicaoBusca,
    RequisicaoBuscaJanela,
    RequisicaoBuscaPorLocal,
    RespostaBusca,
    RespostaBuscaJanela,
    RespostaBuscaPorLocal,
)
from app.services.voos.busca import buscar_voos
from app.services.voos.busca_janela import buscar_janela
from app.services.voos.busca_por_local import buscar_voos_por_local

roteador = APIRouter(prefix="/api/v1", tags=["buscar"])


@roteador.post("/buscar", response_model=RespostaBusca)
def buscar(requisicao: RequisicaoBusca) -> RespostaBusca:
    return buscar_voos(requisicao)


@roteador.post("/buscar/janela", response_model=RespostaBuscaJanela)
def buscar_janela_endpoint(requisicao: RequisicaoBuscaJanela) -> RespostaBuscaJanela:
    return buscar_janela(requisicao)


@roteador.post("/buscar/por-local", response_model=RespostaBuscaPorLocal)
def buscar_por_local(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
    return buscar_voos_por_local(requisicao)
