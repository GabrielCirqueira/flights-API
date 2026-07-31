from fastapi import HTTPException
from fli.models import Airport, MaxStops, SeatType, SortBy

MAPA_MAX_ESCALAS = {
    "ANY": MaxStops.ANY,
    "NON_STOP": MaxStops.NON_STOP,
    "ONE_STOP": MaxStops.ONE_STOP_OR_FEWER,
    "TWO_PLUS_STOPS": MaxStops.TWO_OR_FEWER_STOPS,
}

MAPA_CLASSE = {
    "ECONOMY": SeatType.ECONOMY,
    "PREMIUM_ECONOMY": SeatType.PREMIUM_ECONOMY,
    "BUSINESS": SeatType.BUSINESS,
    "FIRST": SeatType.FIRST,
}

MAPA_ORDENACAO = {
    "CHEAPEST": SortBy.CHEAPEST,
    "BEST": SortBy.BEST,
    "TOP_FLIGHTS": SortBy.TOP_FLIGHTS,
    "DURATION": SortBy.DURATION,
    "DEPARTURE_TIME": SortBy.DEPARTURE_TIME,
    "ARRIVAL_TIME": SortBy.ARRIVAL_TIME,
}


def resolver_aeroporto(codigo: str) -> Airport:
    aeroporto = getattr(Airport, codigo, None)
    if aeroporto is None:
        raise HTTPException(
            status_code=422,
            detail=f"Código IATA desconhecido para o fli: {codigo}",
        )
    return aeroporto
