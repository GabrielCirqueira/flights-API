from datetime import date, datetime, timezone
from urllib.parse import urlencode

from fli.models.google_flights.base import FlightResult

from app.core.config import configuracoes
from app.schemas.voos import OfertaVooSaida, TrechoVooSaida


def url_google_flights(
    origem: str,
    destino: str,
    data_partida: date,
    data_retorno: date | None = None,
) -> str:
    if data_retorno:
        query = (
            f"Flights from {origem} to {destino} on {data_partida.isoformat()} "
            f"returning {data_retorno.isoformat()}"
        )
    else:
        query = f"Flights from {origem} to {destino} on {data_partida.isoformat()} one way"

    parametros = urlencode(
        {
            "q": query,
            "hl": configuracoes.IDIOMA_PADRAO,
            "gl": configuracoes.PAIS_PADRAO,
            "curr": configuracoes.MOEDA_PADRAO,
        }
    )
    return f"https://www.google.com/travel/flights?{parametros}"


def mapear_trecho(trecho) -> TrechoVooSaida:
    return TrechoVooSaida(
        companhia_aerea=trecho.airline.value if hasattr(trecho.airline, "value") else str(trecho.airline),
        nome_companhia_aerea=getattr(trecho, "airline_name", None),
        numero_voo=trecho.flight_number,
        aeroporto_partida=trecho.departure_airport.value
        if hasattr(trecho.departure_airport, "value")
        else str(trecho.departure_airport),
        aeroporto_chegada=trecho.arrival_airport.value
        if hasattr(trecho.arrival_airport, "value")
        else str(trecho.arrival_airport),
        data_hora_partida=trecho.departure_datetime,
        data_hora_chegada=trecho.arrival_datetime,
        duracao_minutos=trecho.duration,
        aeronave=trecho.aircraft,
        companhia_operadora=trecho.operating_airline.value
        if hasattr(trecho.operating_airline, "value")
        else (str(trecho.operating_airline) if trecho.operating_airline else None),
    )


def mapear_oferta(
    voo: FlightResult | tuple[FlightResult, ...] | list[FlightResult],
    origem: str,
    destino: str,
    data_partida: date,
    moeda: str,
    data_retorno: date | None = None,
) -> OfertaVooSaida | None:
    if isinstance(voo, tuple | list):
        segmentos = [s for s in voo if isinstance(s, FlightResult)]
        if not segmentos:
            return None

        outbound = segmentos[0]
        preco_val = None
        for seg in reversed(segmentos):
            if seg.price is not None:
                preco_val = seg.price
                break

        if preco_val is None or float(preco_val) <= 0.0:
            return None

        preco = float(preco_val)
        todos_trechos: list[TrechoVooSaida] = []
        for seg in segmentos:
            for leg in seg.legs:
                todos_trechos.append(mapear_trecho(leg))

        duracao_total = sum(seg.duration for seg in segmentos if seg.duration)
        escalas_totais = sum(seg.stops for seg in segmentos if seg.stops is not None)

        comp_principal = (
            outbound.primary_airline.value
            if hasattr(outbound.primary_airline, "value")
            else str(outbound.primary_airline)
        )

        return OfertaVooSaida(
            preco=preco,
            moeda=outbound.currency or moeda,
            duracao_minutos=duracao_total,
            escalas=escalas_totais,
            companhia_principal=comp_principal,
            nome_companhia_principal=outbound.primary_airline_name,
            trechos=todos_trechos,
            url_busca_google_flights=url_google_flights(origem, destino, data_partida, data_retorno),
            encontrado_em=datetime.now(timezone.utc),
            fonte="fli",
        )

    if voo.price is None or float(voo.price) <= 0.0:
        return None

    return OfertaVooSaida(
        preco=float(voo.price),
        moeda=voo.currency or moeda,
        duracao_minutos=voo.duration,
        escalas=voo.stops,
        companhia_principal=voo.primary_airline.value
        if hasattr(voo.primary_airline, "value")
        else str(voo.primary_airline),
        nome_companhia_principal=voo.primary_airline_name,
        trechos=[mapear_trecho(leg) for leg in voo.legs],
        url_busca_google_flights=url_google_flights(origem, destino, data_partida, data_retorno),
        encontrado_em=datetime.now(timezone.utc),
        fonte="fli",
    )
