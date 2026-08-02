from fastapi import APIRouter, Query

from app.schemas.cidades import RespostaListaCidades
from app.services.cidades.consulta import listar_cidades

roteador = APIRouter(prefix="/api/v1", tags=["cidades"])


@roteador.get("/cidades", response_model=RespostaListaCidades)
@roteador.get("/cities", response_model=RespostaListaCidades)
@roteador.get("/cidades/buscar", response_model=RespostaListaCidades)
@roteador.get("/cities/search", response_model=RespostaListaCidades)
def listar_cidades_endpoint(
    busca: str | None = Query(
        default=None,
        min_length=1,
        alias="busca",
        description="Busca textual por nome da cidade ou estado (ex: são, goiânia, SP, GO)",
    ),
    query: str | None = Query(
        default=None,
        min_length=1,
        alias="query",
        description="Alias para busca textual",
    ),
    q: str | None = Query(
        default=None,
        min_length=1,
        alias="q",
        description="Alias curto para busca textual",
    ),
    estado: str | None = Query(
        default=None,
        min_length=1,
        alias="estado",
        description="Filtro estrito por estado / sigla UF (ex: SP ou GO)",
    ),
    uf: str | None = Query(
        default=None,
        min_length=1,
        alias="uf",
        description="Alias para filtro por estado",
    ),
    pais: str | None = Query(
        default=None,
        min_length=1,
        description="Filtro estrito por país (ex: Brasil)",
    ),
    limite: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Quantidade máxima de resultados a retornar",
    ),
) -> RespostaListaCidades:
    termo_busca = busca or query or q
    filtro_estado = estado or uf

    return listar_cidades(
        busca=termo_busca,
        estado=filtro_estado,
        pais=pais,
        limite=limite,
    )
