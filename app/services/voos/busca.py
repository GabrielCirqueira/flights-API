import logging

from fastapi import HTTPException
from fli.models import FlightSearchFilters, FlightSegment, PassengerInfo
from fli.models.google_flights.base import TripType
from fli.search.flights import SearchFlights

from app.core.config import configuracoes
from app.schemas.voos import OfertaVooSaida, RequisicaoBusca, RespostaBusca
from app.services.fli.adaptadores import MAPA_CLASSE, MAPA_MAX_ESCALAS, MAPA_ORDENACAO, resolver_aeroporto
from app.services.voos.mapeamento import mapear_oferta

logger = logging.getLogger("flights_api.voos.busca")


def buscar_voos(requisicao: RequisicaoBusca) -> RespostaBusca:
    origem = resolver_aeroporto(requisicao.origem)
    destino = resolver_aeroporto(requisicao.destino)

    segmentos = [
        FlightSegment(
            departure_airport=[[origem, 0]],
            arrival_airport=[[destino, 0]],
            travel_date=requisicao.data_partida.isoformat(),
        )
    ]
    tipo_viagem = TripType.ONE_WAY

    if requisicao.data_retorno:
        segmentos.append(
            FlightSegment(
                departure_airport=[[destino, 0]],
                arrival_airport=[[origem, 0]],
                travel_date=requisicao.data_retorno.isoformat(),
            )
        )
        tipo_viagem = TripType.ROUND_TRIP

    filtros = FlightSearchFilters(
        trip_type=tipo_viagem,
        passenger_info=PassengerInfo(adults=requisicao.adultos, children=requisicao.criancas),
        flight_segments=segmentos,
        seat_type=MAPA_CLASSE.get(requisicao.classe_cabine.upper(), MAPA_CLASSE["ECONOMY"]),
        stops=MAPA_MAX_ESCALAS.get(requisicao.maximo_escalas.upper(), MAPA_MAX_ESCALAS["ANY"]),
        sort_by=MAPA_ORDENACAO.get(requisicao.ordenar_por.upper(), MAPA_ORDENACAO["CHEAPEST"]),
    )

    try:
        resultados = SearchFlights().search(
            filtros,
            top_n=requisicao.limite_top,
            currency=configuracoes.MOEDA_PADRAO,
            language=configuracoes.IDIOMA_PADRAO,
            country=configuracoes.PAIS_PADRAO,
        )
    except Exception:
        logger.exception(
            "fli.falha_busca origem=%s destino=%s data=%s",
            requisicao.origem,
            requisicao.destino,
            requisicao.data_partida,
        )
        raise HTTPException(status_code=502, detail="upstream_search_failed") from None

    ofertas: list[OfertaVooSaida] = []
    if resultados:
        for item in resultados:
            oferta = mapear_oferta(
                item, requisicao.origem, requisicao.destino, requisicao.data_partida, configuracoes.MOEDA_PADRAO
            )
            if oferta is not None:
                ofertas.append(oferta)

    return RespostaBusca(
        origem=requisicao.origem,
        destino=requisicao.destino,
        data_partida=requisicao.data_partida.isoformat(),
        data_retorno=requisicao.data_retorno.isoformat() if requisicao.data_retorno else None,
        moeda=configuracoes.MOEDA_PADRAO,
        ofertas=ofertas,
        total=len(ofertas),
    )
