import logging
from datetime import date

from fastapi import HTTPException
from fli.models import DateSearchFilters, FlightSegment, PassengerInfo
from fli.models.google_flights.base import TripType
from fli.search.dates import SearchDates

from app.core.config import configuracoes
from app.schemas.voos import DataPrecoSaida, OfertaVooSaida, RequisicaoBusca, RequisicaoBuscaJanela, RespostaBuscaJanela
from app.services.fli.adaptadores import MAPA_CLASSE, MAPA_MAX_ESCALAS, resolver_aeroporto
from app.services.voos.busca import buscar_voos

logger = logging.getLogger("flights_api.voos.busca_janela")


def buscar_janela(requisicao: RequisicaoBuscaJanela) -> RespostaBuscaJanela:
    origem = resolver_aeroporto(requisicao.origem)
    destino = resolver_aeroporto(requisicao.destino)

    filtros_data = DateSearchFilters(
        trip_type=TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=requisicao.adultos),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origem, 0]],
                arrival_airport=[[destino, 0]],
                travel_date=requisicao.data_inicio.isoformat(),
            )
        ],
        seat_type=MAPA_CLASSE.get(requisicao.classe_cabine.upper(), MAPA_CLASSE["ECONOMY"]),
        stops=MAPA_MAX_ESCALAS.get(requisicao.maximo_escalas.upper(), MAPA_MAX_ESCALAS["ANY"]),
        from_date=requisicao.data_inicio.isoformat(),
        to_date=requisicao.data_fim.isoformat(),
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
            requisicao.origem,
            requisicao.destino,
            requisicao.data_inicio,
            requisicao.data_fim,
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

    mais_baratas_expandidas: list[OfertaVooSaida] = []
    for dp in por_data[: requisicao.expandir_top]:
        requisicao_expansao = RequisicaoBusca(
            origem=requisicao.origem,
            destino=requisicao.destino,
            data_partida=date.fromisoformat(dp.data),
            adultos=requisicao.adultos,
            classe_cabine=requisicao.classe_cabine,
            maximo_escalas=requisicao.maximo_escalas,
            limite_top=3,
        )
        try:
            expandida = buscar_voos(requisicao_expansao)
        except HTTPException:
            continue
        if expandida.ofertas:
            mais_baratas_expandidas.append(expandida.ofertas[0])

    return RespostaBuscaJanela(
        origem=requisicao.origem,
        destino=requisicao.destino,
        data_inicio=requisicao.data_inicio.isoformat(),
        data_fim=requisicao.data_fim.isoformat(),
        moeda=configuracoes.MOEDA_PADRAO,
        por_data=por_data,
        mais_baratas_expandidas=mais_baratas_expandidas,
    )
