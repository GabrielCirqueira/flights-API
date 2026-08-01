from datetime import date, datetime, timezone
from urllib.parse import urlencode

from fli.models.google_flights.base import FlightResult

from app.core.config import configuracoes
from app.schemas.voos import OfertaVooSaida, ParadaRotaSaida, TrechoVooSaida
from app.services.aeroportos.texto import obter_cidade_por_iata


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


def _iata_aeroporto(aeroporto) -> str:
    if hasattr(aeroporto, "name"):
        return aeroporto.name
    return str(aeroporto)


def _nome_aeroporto(aeroporto) -> str:
    if hasattr(aeroporto, "value"):
        return aeroporto.value
    return str(aeroporto)


def _parada_rota(iata: str) -> ParadaRotaSaida:
    return ParadaRotaSaida(iata=iata, cidade=obter_cidade_por_iata(iata))


def _montar_info_rota(
    trechos: list[TrechoVooSaida], escalas: int
) -> tuple[bool, bool, list[ParadaRotaSaida], list[ParadaRotaSaida]]:
    if not trechos:
        return True, False, [], []

    codigos = [trechos[0].iata_partida]
    for trecho in trechos:
        codigos.append(trecho.iata_chegada)

    rota_iata = [_parada_rota(codigo) for codigo in codigos]

    direto = escalas == 0 and len(trechos) == 1
    com_conexao = not direto
    aeroportos_conexao = rota_iata[1:-1] if len(rota_iata) > 2 else []

    return direto, com_conexao, rota_iata, aeroportos_conexao


def mapear_trecho(trecho) -> TrechoVooSaida:
    return TrechoVooSaida(
        iata_partida=_iata_aeroporto(trecho.departure_airport),
        iata_chegada=_iata_aeroporto(trecho.arrival_airport),
        aeroporto_partida=_nome_aeroporto(trecho.departure_airport),
        aeroporto_chegada=_nome_aeroporto(trecho.arrival_airport),
        companhia_aerea=trecho.airline.value if hasattr(trecho.airline, "value") else str(trecho.airline),
        nome_companhia_aerea=getattr(trecho, "airline_name", None),
        numero_voo=trecho.flight_number,
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
        direto, com_conexao, rota_iata, aeroportos_conexao = _montar_info_rota(todos_trechos, escalas_totais)

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
            direto=direto,
            com_conexao=com_conexao,
            rota_iata=rota_iata,
            aeroportos_conexao=aeroportos_conexao,
            companhia_principal=comp_principal,
            nome_companhia_principal=outbound.primary_airline_name,
            trechos=todos_trechos,
            url_busca_google_flights=url_google_flights(origem, destino, data_partida, data_retorno),
            encontrado_em=datetime.now(timezone.utc),
            fonte="fli",
        )

    if voo.price is None or float(voo.price) <= 0.0:
        return None

    trechos = [mapear_trecho(leg) for leg in voo.legs]
    direto, com_conexao, rota_iata, aeroportos_conexao = _montar_info_rota(trechos, voo.stops)

    return OfertaVooSaida(
        preco=float(voo.price),
        moeda=voo.currency or moeda,
        duracao_minutos=voo.duration,
        escalas=voo.stops,
        direto=direto,
        com_conexao=com_conexao,
        rota_iata=rota_iata,
        aeroportos_conexao=aeroportos_conexao,
        companhia_principal=voo.primary_airline.value
        if hasattr(voo.primary_airline, "value")
        else str(voo.primary_airline),
        nome_companhia_principal=voo.primary_airline_name,
        trechos=trechos,
        url_busca_google_flights=url_google_flights(origem, destino, data_partida, data_retorno),
        encontrado_em=datetime.now(timezone.utc),
        fonte="fli",
    )
