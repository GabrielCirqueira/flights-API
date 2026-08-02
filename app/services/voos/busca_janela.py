import logging
from datetime import date

from fastapi import HTTPException
from fli.models import DateSearchFilters, FlightSegment, PassengerInfo
from fli.models.google_flights.base import TripType
from fli.search.dates import SearchDates

from app.core.config import configuracoes
from app.schemas.voos import (
    DataPrecoSaida,
    OfertaVooSaida,
    RequisicaoBusca,
    RequisicaoBuscaAberta,
    RequisicaoBuscaJanela,
    RespostaBuscaJanela,
)
from app.services.fli.adaptadores import MAPA_CLASSE, MAPA_MAX_ESCALAS, resolver_aeroporto
from app.services.voos.busca import buscar_voos
from app.services.voos.janela_util import resolver_intervalo_janela

logger = logging.getLogger("flights_api.voos.busca_janela")


def _buscar_precos_por_dia(
    origem_iata: str,
    destino_iata: str,
    data_inicio: date,
    data_fim: date,
    adultos: int,
    classe_cabine: str,
    maximo_escalas: str,
) -> list[DataPrecoSaida]:
    origem = resolver_aeroporto(origem_iata)
    destino = resolver_aeroporto(destino_iata)

    filtros_data = DateSearchFilters(
        trip_type=TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=adultos),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origem, 0]],
                arrival_airport=[[destino, 0]],
                travel_date=data_inicio.isoformat(),
            )
        ],
        seat_type=MAPA_CLASSE.get(classe_cabine.upper(), MAPA_CLASSE["ECONOMY"]),
        stops=MAPA_MAX_ESCALAS.get(maximo_escalas.upper(), MAPA_MAX_ESCALAS["ANY"]),
        from_date=data_inicio.isoformat(),
        to_date=data_fim.isoformat(),
    )

    try:
        precos_datas = SearchDates().search(
            filtros_data,
            currency=configuracoes.MOEDA_PADRAO,
            language=configuracoes.IDIOMA_PADRAO,
            country=configuracoes.PAIS_PADRAO,
        )
    except Exception:
        logger.exception(
            "fli.falha_busca_janela origem=%s destino=%s de=%s ate=%s",
            origem_iata,
            destino_iata,
            data_inicio,
            data_fim,
        )
        raise HTTPException(status_code=502, detail="upstream_search_failed") from None

    por_data: list[DataPrecoSaida] = []
    if precos_datas:
        for dp in precos_datas:
            d = dp.date[0] if isinstance(dp.date, tuple) else dp.date
            por_data.append(
                DataPrecoSaida(
                    data=d.date().isoformat() if hasattr(d, "date") else str(d),
                    preco=dp.price,
                    moeda=dp.currency or configuracoes.MOEDA_PADRAO,
                )
            )

    por_data.sort(key=lambda x: x.preco)
    return por_data


def _expandir_melhores_datas(
    origem_iata: str,
    destino_iata: str,
    por_data: list[DataPrecoSaida],
    expandir_top: int,
    adultos: int,
    classe_cabine: str,
    maximo_escalas: str,
) -> list[OfertaVooSaida]:
    mais_baratas: list[OfertaVooSaida] = []
    for dp in por_data[:expandir_top]:
        requisicao_expansao = RequisicaoBusca(
            origem=origem_iata,
            destino=destino_iata,
            data_partida=date.fromisoformat(dp.data),
            adultos=adultos,
            classe_cabine=classe_cabine,
            maximo_escalas=maximo_escalas,
            limite_top=3,
        )
        try:
            expandida = buscar_voos(requisicao_expansao)
        except HTTPException:
            continue
        if expandida.ofertas:
            mais_baratas.append(expandida.ofertas[0])
    return mais_baratas


def buscar_janela(requisicao: RequisicaoBuscaJanela) -> RespostaBuscaJanela:
    try:
        inicio, fim, dias, aberta = resolver_intervalo_janela(
            requisicao.data_inicio,
            requisicao.data_fim,
            requisicao.janela_dias,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    por_data = _buscar_precos_por_dia(
        requisicao.origem,
        requisicao.destino,
        inicio,
        fim,
        requisicao.adultos,
        requisicao.classe_cabine,
        requisicao.maximo_escalas,
    )

    mais_baratas_expandidas = _expandir_melhores_datas(
        requisicao.origem,
        requisicao.destino,
        por_data,
        requisicao.expandir_top,
        requisicao.adultos,
        requisicao.classe_cabine,
        requisicao.maximo_escalas,
    )

    return RespostaBuscaJanela(
        origem=requisicao.origem,
        destino=requisicao.destino,
        data_inicio=inicio.isoformat(),
        data_fim=fim.isoformat(),
        moeda=configuracoes.MOEDA_PADRAO,
        modo_busca="aberta" if aberta else "janela",
        janela_dias=dias if aberta or requisicao.janela_dias else None,
        por_data=por_data,
        mais_baratas_expandidas=mais_baratas_expandidas,
    )


def buscar_aberta(requisicao: RequisicaoBuscaAberta) -> RespostaBuscaJanela:
    janela = RequisicaoBuscaJanela(
        origem=requisicao.origem,
        destino=requisicao.destino,
        janela_dias=requisicao.janela_dias,
        adultos=requisicao.adultos,
        classe_cabine=requisicao.classe_cabine,
        maximo_escalas=requisicao.maximo_escalas,
        expandir_top=requisicao.expandir_top,
    )
    return buscar_janela(janela)
