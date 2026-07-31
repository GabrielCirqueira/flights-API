from fastapi import APIRouter, Query

from app.schemas.aeroportos import AeroportoSaida, RespostaListaAeroportos
from app.services.aeroportos.consulta import listar_aeroportos, obter_aeroporto_por_codigo

roteador = APIRouter(prefix="/api/v1", tags=["aeroportos"])


@roteador.get("/aeroportos", response_model=RespostaListaAeroportos)
def listar_aeroportos_endpoint(
    busca: str | None = Query(
        default=None,
        min_length=1,
        description="Busca textual ampla por IATA, nome do aeroporto, cidade ou estado (ex: goias ou VIX)",
    ),
    cidade: str | None = Query(
        default=None,
        min_length=1,
        description="Filtro estrito por nome da cidade (ex: Goiânia ou São Paulo)",
    ),
    estado: str | None = Query(
        default=None,
        min_length=1,
        description="Filtro estrito por estado / sigla UF ou por extenso (ex: GO ou Goiás)",
    ),
    pais: str | None = Query(
        default=None,
        min_length=1,
        description="Filtro estrito por país (ex: Brasil ou Espanha)",
    ),
    apenas_principais: bool = Query(
        default=False,
        description="Se verdadeiro, retorna apenas aeroportos comerciais principais",
    ),
    limite: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Quantidade máxima de resultados a retornar",
    ),
) -> RespostaListaAeroportos:
    return listar_aeroportos(
        busca=busca,
        cidade=cidade,
        estado=estado,
        pais=pais,
        apenas_principais=apenas_principais,
        limite=limite,
    )


@roteador.get("/aeroportos/{codigo_iata}", response_model=AeroportoSaida)
def obter_aeroporto(codigo_iata: str) -> AeroportoSaida:
    return obter_aeroporto_por_codigo(codigo_iata)
