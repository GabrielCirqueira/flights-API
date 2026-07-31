from fastapi import APIRouter

from app.schemas.request import RequisicaoBusca, RequisicaoBuscaJanela, RequisicaoBuscaPorLocal
from app.schemas.response import RespostaBusca, RespostaBuscaJanela, RespostaBuscaPorLocal
from app.services import servico_fli

roteador = APIRouter(prefix="/api/v1", tags=["buscar"])

@roteador.post("/buscar", response_model=RespostaBusca)
def buscar(requisicao: RequisicaoBusca) -> RespostaBusca:
    return servico_fli.buscar_voos(requisicao)

@roteador.post("/buscar/janela", response_model=RespostaBuscaJanela)
def buscar_janela(requisicao: RequisicaoBuscaJanela) -> RespostaBuscaJanela:
    return servico_fli.buscar_janela(requisicao)

@roteador.post("/buscar/por-local", response_model=RespostaBuscaPorLocal)
def buscar_por_local(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
    return servico_fli.buscar_voos_por_local(requisicao)