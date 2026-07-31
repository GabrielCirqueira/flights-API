
import concurrent.futures
import logging
import time
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from fastapi import HTTPException
from fli.models import (
    Airport,
    DateSearchFilters,
    FlightSearchFilters,
    FlightSegment,
    MaxStops,
    PassengerInfo,
    SeatType,
    SortBy,
)
from fli.models.google_flights.base import FlightResult, TripType
from fli.search.dates import SearchDates
from fli.search.flights import SearchFlights

from app.core.config import configuracoes
from app.schemas.request import RequisicaoBusca, RequisicaoBuscaJanela, RequisicaoBuscaPorLocal, TipoLocal
from app.schemas.response import (
    AeroportoSaida,
    CombinacaoVooSaida,
    DataPrecoSaida,
    OfertaVooSaida,
    RespostaBusca,
    RespostaBuscaJanela,
    RespostaBuscaPorLocal,
    RespostaListaAeroportos,
    TrechoVooSaida,
)

logger = logging.getLogger("flights_api.servico_fli")

_MAPA_MAX_ESCALAS = {
    "ANY": MaxStops.ANY,
    "NON_STOP": MaxStops.NON_STOP,
    "ONE_STOP": MaxStops.ONE_STOP_OR_FEWER,
    "TWO_PLUS_STOPS": MaxStops.TWO_OR_FEWER_STOPS,
}

_MAPA_CLASSE = {
    "ECONOMY": SeatType.ECONOMY,
    "PREMIUM_ECONOMY": SeatType.PREMIUM_ECONOMY,
    "BUSINESS": SeatType.BUSINESS,
    "FIRST": SeatType.FIRST,
}

_MAPA_ORDENACAO = {
    "CHEAPEST": SortBy.CHEAPEST,
    "BEST": SortBy.BEST,
    "TOP_FLIGHTS": SortBy.TOP_FLIGHTS,
    "DURATION": SortBy.DURATION,
    "DEPARTURE_TIME": SortBy.DEPARTURE_TIME,
    "ARRIVAL_TIME": SortBy.ARRIVAL_TIME,
}

def _resolver_aeroporto(codigo: str) -> Airport:
    aeroporto = getattr(Airport, codigo, None)
    if aeroporto is None:
        raise HTTPException(
            status_code=422,
            detail=f"Código IATA desconhecido para o fli: {codigo}",
        )
    return aeroporto

def _url_google_flights(origem: str, destino: str, data_partida: date) -> str:
    parametros = urlencode(
        {
            "hl": configuracoes.IDIOMA_PADRAO,
            "gl": configuracoes.PAIS_PADRAO,
            "curr": configuracoes.MOEDA_PADRAO,
        }
    )
    query = f"Flights to {destino} from {origem} on {data_partida.isoformat()}"
    return f"https://www.google.com/travel/flights?q={query}&{parametros}".replace(" ", "+")

def _mapear_trecho(trecho) -> TrechoVooSaida:
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

def _mapear_oferta(
    voo: FlightResult | tuple[FlightResult, ...] | list[FlightResult],
    origem: str,
    destino: str,
    data_partida: date,
    moeda: str,
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
                todos_trechos.append(_mapear_trecho(leg))

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
            url_busca_google_flights=_url_google_flights(origem, destino, data_partida),
            encontrado_em=datetime.now(timezone.utc),
            fonte="fli",
        )
    else:
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
            trechos=[_mapear_trecho(leg) for leg in voo.legs],
            url_busca_google_flights=_url_google_flights(origem, destino, data_partida),
            encontrado_em=datetime.now(timezone.utc),
            fonte="fli",
        )

def buscar_voos(requisicao: RequisicaoBusca) -> RespostaBusca:

    origem = _resolver_aeroporto(requisicao.origem)
    destino = _resolver_aeroporto(requisicao.destino)

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
        seat_type=_MAPA_CLASSE.get(requisicao.classe_cabine.upper(), SeatType.ECONOMY),
        stops=_MAPA_MAX_ESCALAS.get(requisicao.maximo_escalas.upper(), MaxStops.ANY),
        sort_by=_MAPA_ORDENACAO.get(requisicao.ordenar_por.upper(), SortBy.CHEAPEST),
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
            oferta = _mapear_oferta(
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

def buscar_janela(requisicao: RequisicaoBuscaJanela) -> RespostaBuscaJanela:

    origem = _resolver_aeroporto(requisicao.origem)
    destino = _resolver_aeroporto(requisicao.destino)

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
        seat_type=_MAPA_CLASSE.get(requisicao.classe_cabine.upper(), SeatType.ECONOMY),
        stops=_MAPA_MAX_ESCALAS.get(requisicao.maximo_escalas.upper(), MaxStops.ANY),
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

_ESTADOS_BRASIL: dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}

def _remover_acentos(texto: str | None) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()

def _obter_nome_estado(sigla_ou_nome: str | None) -> str:
    if not sigla_ou_nome:
        return ""
    sigla = sigla_ou_nome.strip().upper()
    return _ESTADOS_BRASIL.get(sigla, sigla_ou_nome)

_MAPEAMENTO_AEROPORTOS: dict[str, tuple[str, str | None, str, bool, str | None]] = {
    "VIX": ("Vitória", "ES", "Brasil", True, "Aeroporto de Vitória — principal aeroporto comercial do Espírito Santo"),
    "GRU": (
        "São Paulo",
        "SP",
        "Brasil",
        True,
        "Aeroporto Internacional de Guarulhos — maior hub de voos nacionais e internacionais de SP",
    ),
    "CGH": (
        "São Paulo",
        "SP",
        "Brasil",
        True,
        "Aeroporto de Congonhas — próximo ao centro de SP, foco em ponte aérea e voos nacionais",
    ),
    "VCP": (
        "Campinas",
        "SP",
        "Brasil",
        True,
        "Aeroporto de Viracopos (Campinas) — hub principal da Azul Linhas Aéreas em SP",
    ),
    "GIG": (
        "Rio de Janeiro",
        "RJ",
        "Brasil",
        True,
        "Aeroporto Internacional do Galeão — voos internacionais e conexões no RJ",
    ),
    "SDU": (
        "Rio de Janeiro",
        "RJ",
        "Brasil",
        True,
        "Aeroporto Santos Dumont — próximo ao centro do RJ, ponte aérea com SP",
    ),
    "CNF": (
        "Belo Horizonte",
        "MG",
        "Brasil",
        True,
        "Aeroporto Internacional de Confins — maior hub de voos comerciais de MG",
    ),
    "PLU": (
        "Belo Horizonte",
        "MG",
        "Brasil",
        False,
        "Aeroporto da Pampulha — voos executivos e regionais, poucas opções comerciais",
    ),
    "SSA": (
        "Salvador",
        "BA",
        "Brasil",
        True,
        "Aeroporto Internacional de Salvador — principal porta de entrada da Bahia",
    ),
    "REC": ("Recife", "PE", "Brasil", True, "Aeroporto Internacional do Recife — hub de conexões do Nordeste"),
    "FOR": ("Fortaleza", "CE", "Brasil", True, "Aeroporto Internacional de Fortaleza — hub comercial do Ceará"),
    "BSB": (
        "Brasília",
        "DF",
        "Brasil",
        True,
        "Aeroporto Internacional de Brasília — hub central de conexões no Brasil",
    ),
    "CWB": ("Curitiba", "PR", "Brasil", True, "Aeroporto Internacional Afonso Pena (Curitiba) — principal de PR"),
    "POA": (
        "Porto Alegre",
        "RS",
        "Brasil",
        True,
        "Aeroporto Internacional Salgado Filho (Porto Alegre) — principal de RS",
    ),
    "FLN": (
        "Florianópolis",
        "SC",
        "Brasil",
        True,
        "Aeroporto Internacional Hercílio Luz (Florianópolis) — principal de SC",
    ),
    "MAO": ("Manaus", "AM", "Brasil", True, "Aeroporto Internacional de Manaus — principal hub da Região Norte"),
    "BEL": ("Belém", "PA", "Brasil", True, "Aeroporto Internacional de Belém — conexões do Pará e Região Norte"),
    "GYN": ("Goiânia", "GO", "Brasil", True, "Aeroporto Santa Genoveva (Goiânia) — principal aeroporto de Goiás"),
    "CLV": ("Caldas Novas", "GO", "Brasil", True, "Aeroporto de Caldas Novas — voos turísticos e regionais"),
    "RRV": ("Rio Verde", "GO", "Brasil", False, "Aeroporto de Rio Verde — aviação regional e executiva"),
    "CGB": ("Cuiabá", "MT", "Brasil", True, "Aeroporto Internacional de Cuiabá — principal de MT"),
    "NAT": ("Natal", "RN", "Brasil", True, "Aeroporto Internacional de Natal — principal de RN"),
    "MCZ": ("Maceió", "AL", "Brasil", True, "Aeroporto Internacional de Maceió — principal de AL"),
    "JPA": ("João Pessoa", "PB", "Brasil", True, "Aeroporto Internacional de João Pessoa — principal de PB"),
    "AJU": ("Aracaju", "SE", "Brasil", True, "Aeroporto de Aracaju — principal de SE"),
    "NVT": (
        "Navegantes",
        "SC",
        "Brasil",
        True,
        "Aeroporto de Navegantes — acesso a Balneário Camboriú e Vale do Itajaí",
    ),
    "JOI": ("Joinville", "SC", "Brasil", True, "Aeroporto de Joinville — voos comerciais em SC"),
    "IGU": (
        "Foz do Iguaçu",
        "PR",
        "Brasil",
        True,
        "Aeroporto Internacional de Foz do Iguaçu — voos turísticos na tríplice fronteira",
    ),
    "LDB": ("Londrina", "PR", "Brasil", True, "Aeroporto de Londrina — voos comerciais no norte do PR"),
    "UDI": ("Uberlândia", "MG", "Brasil", True, "Aeroporto de Uberlândia — principal hub do Triângulo Mineiro"),
    "RAO": ("Ribeirão Preto", "SP", "Brasil", True, "Aeroporto de Ribeirão Preto — voos comerciais no interior de SP"),
    "BPS": ("Porto Seguro", "BA", "Brasil", True, "Aeroporto de Porto Seguro — voos turísticos no sul da Bahia"),
    "VDC": (
        "Vitória da Conquista",
        "BA",
        "Brasil",
        True,
        "Aeroporto de Vitória da Conquista — voos no sudoeste baiano",
    ),
    "IOS": ("Ilhéus", "BA", "Brasil", True, "Aeroporto de Ilhéus — voos turísticos no litoral baiano"),
    "MCP": ("Macapá", "AP", "Brasil", True, "Aeroporto de Macapá — principal do Amapá"),
    "BVB": ("Boa Vista", "RR", "Brasil", True, "Aeroporto de Boa Vista — principal de Roraima"),
    "RBR": ("Rio Branco", "AC", "Brasil", True, "Aeroporto de Rio Branco — principal do Acre"),
    "PVH": ("Porto Velho", "RO", "Brasil", True, "Aeroporto de Porto Velho — principal de Rondônia"),
    "PMW": ("Palmas", "TO", "Brasil", True, "Aeroporto de Palmas — principal do Tocantins"),
    "SLZ": ("São Luís", "MA", "Brasil", True, "Aeroporto de São Luís — principal do Maranhão"),
    "THE": ("Teresina", "PI", "Brasil", True, "Aeroporto de Teresina — principal do Piauí"),
    "IMP": ("Imperatriz", "MA", "Brasil", True, "Aeroporto de Imperatriz — voos no interior do Maranhão"),
    "PNZ": ("Petrolina", "PE", "Brasil", True, "Aeroporto de Petrolina — voos no Vale do São Francisco"),
    "JDO": ("Juazeiro do Norte", "CE", "Brasil", True, "Aeroporto de Juazeiro do Norte — voos no Cariri cearense"),
    "CPV": ("Campina Grande", "PB", "Brasil", True, "Aeroporto de Campina Grande — voos no interior da Paraíba"),
    "XAP": ("Chapecó", "SC", "Brasil", True, "Aeroporto de Chapecó — principal do oeste catarinense"),
    "CXJ": ("Caxias do Sul", "RS", "Brasil", True, "Aeroporto de Caxias do Sul — voos na serra gaúcha"),
    "EZE": (
        "Buenos Aires",
        None,
        "Argentina",
        True,
        "Aeroporto Internacional de Ezeiza — voos internacionais em Buenos Aires",
    ),
    "AEP": (
        "Buenos Aires",
        None,
        "Argentina",
        True,
        "Aeroparque Jorge Newbery — voos regionais no centro de Buenos Aires",
    ),
    "MVD": ("Montevidéu", None, "Uruguai", True, "Aeroporto Internacional de Carrasco — principal do Uruguai"),
    "SCL": ("Santiago", None, "Chile", True, "Aeroporto Internacional de Santiago — principal do Chile"),
    "LIM": ("Lima", None, "Peru", True, "Aeroporto Internacional Jorge Chávez — principal hub do Peru"),
    "BOG": ("Bogotá", None, "Colômbia", True, "Aeroporto Internacional El Dorado — principal hub da Colômbia"),
    "MIA": ("Miami", "FL", "Estados Unidos", True, "Miami International Airport — principal porta para Flórida"),
    "MCO": ("Orlando", "FL", "Estados Unidos", True, "Orlando International Airport — voos para parques e turismo"),
    "JFK": (
        "Nova York",
        "NY",
        "Estados Unidos",
        True,
        "John F. Kennedy International Airport — maior hub internacional de NY",
    ),
    "LHR": ("Londres", None, "Reino Unido", True, "Heathrow Airport — maior aeroporto de Londres"),
    "CDG": ("Paris", None, "França", True, "Charles de Gaulle Airport — principal de Paris"),
    "MAD": ("Madri", None, "Espanha", True, "Adolfo Suárez Madrid-Barajas Airport — principal da Espanha"),
    "LIS": ("Lisboa", None, "Portugal", True, "Humberto Delgado Airport — principal porta de entrada de Portugal"),
    "FRA": ("Frankfurt", None, "Alemanha", True, "Frankfurt Airport — principal hub da Alemanha"),
}

def _construir_aeroporto_saida(item) -> AeroportoSaida:
    codigo = item.name
    nome = item.value
    info = _MAPEAMENTO_AEROPORTOS.get(codigo)
    if info:
        cidade, estado, pais, principal, desc = info
        return AeroportoSaida(
            codigo_iata=codigo,
            nome=nome,
            cidade=cidade,
            estado=estado,
            pais=pais,
            principal=principal,
            descricao_curta=desc,
        )
    return AeroportoSaida(codigo_iata=codigo, nome=nome, principal=False)

class _ItemIndiceAeroporto:
    __slots__ = (
        "aeroporto_out",
        "codigo_iata",
        "codigo_iata_norm",
        "nome_norm",
        "cidade_norm",
        "estado_uf_norm",
        "estado_nome_norm",
        "pais_norm",
    )

    def __init__(self, item: Airport):
        aero = _construir_aeroporto_saida(item)
        self.aeroporto_out = aero
        self.codigo_iata = item.name
        self.codigo_iata_norm = _remover_acentos(item.name)
        self.nome_norm = _remover_acentos(item.value)
        self.cidade_norm = _remover_acentos(aero.cidade)
        self.estado_uf_norm = _remover_acentos(aero.estado)
        self.estado_nome_norm = _remover_acentos(_obter_nome_estado(aero.estado))
        self.pais_norm = _remover_acentos(aero.pais)

_INDICE_AEROPORTOS_CACHE: list[_ItemIndiceAeroporto] = [_ItemIndiceAeroporto(item) for item in Airport]

def listar_aeroportos(
    busca: str | None = None,
    cidade: str | None = None,
    estado: str | None = None,
    pais: str | None = None,
    apenas_principais: bool = False,
    limite: int = 20,
) -> RespostaListaAeroportos:
    termo_norm = _remover_acentos(busca)
    termo_upper = busca.strip().upper() if busca else ""
    cidade_norm = _remover_acentos(cidade)
    estado_norm = _remover_acentos(estado)
    pais_norm = _remover_acentos(pais)

    exatos_cidade_principal = []
    prefixos_cidade_principal = []
    outros_principais = []
    exatos_iata = []
    inicio_iata = []
    outros_match = []

    for item_idx in _INDICE_AEROPORTOS_CACHE:
        aero_out = item_idx.aeroporto_out

        if apenas_principais and not aero_out.principal:
            continue

        if cidade_norm and cidade_norm != item_idx.cidade_norm:
            continue

        if estado_norm:
            if estado_norm != item_idx.estado_uf_norm and estado_norm != item_idx.estado_nome_norm:
                continue

        if pais_norm and pais_norm != item_idx.pais_norm:
            continue

        if not termo_norm:
            outros_match.append(aero_out)
            continue

        cidade_aero_norm = item_idx.cidade_norm
        nome_aero_norm = item_idx.nome_norm
        codigo = item_idx.codigo_iata

        match_cidade_exata = (cidade_aero_norm == termo_norm) if cidade_aero_norm else False
        match_cidade_inicio = (cidade_aero_norm.startswith(termo_norm)) if cidade_aero_norm else False
        match_cidade_contem = (termo_norm in cidade_aero_norm) if cidade_aero_norm else False
        match_estado_exato = (termo_norm == item_idx.estado_uf_norm) or (termo_norm == item_idx.estado_nome_norm)
        match_nome = termo_norm in nome_aero_norm
        match_iata = codigo == termo_upper
        match_inicio_iata = codigo.startswith(termo_upper)

        if aero_out.principal and (match_cidade_exata or match_iata or match_estado_exato):
            exatos_cidade_principal.append(aero_out)
        elif aero_out.principal and match_cidade_inicio:
            prefixos_cidade_principal.append(aero_out)
        elif aero_out.principal and (match_cidade_contem or match_nome):
            outros_principais.append(aero_out)
        elif match_iata:
            exatos_iata.append(aero_out)
        elif match_inicio_iata:
            inicio_iata.append(aero_out)
        elif match_cidade_contem or match_estado_exato or match_nome:
            outros_match.append(aero_out)

    todos = (
        exatos_cidade_principal
        + prefixos_cidade_principal
        + outros_principais
        + exatos_iata
        + inicio_iata
        + outros_match
    )
    return RespostaListaAeroportos(total=len(todos), aeroportos=todos[:limite])

def obter_aeroporto_por_codigo(codigo_iata: str) -> AeroportoSaida:
    codigo = codigo_iata.strip().upper()
    aeroporto = getattr(Airport, codigo, None)
    if aeroporto is None:
        raise HTTPException(
            status_code=404,
            detail=f"Aeroporto com código IATA '{codigo}' não encontrado.",
        )
    return _construir_aeroporto_saida(aeroporto)

_CACHE_BUSCA_VOOS: dict[str, tuple[float, RespostaBusca]] = {}
_TTL_CACHE_SEGUNDOS = 300.0

def _obter_busca_cacheada(chave: str) -> RespostaBusca | None:
    if chave in _CACHE_BUSCA_VOOS:
        ts, resposta = _CACHE_BUSCA_VOOS[chave]
        if time.time() - ts < _TTL_CACHE_SEGUNDOS:
            return resposta
        del _CACHE_BUSCA_VOOS[chave]
    return None

def _salvar_busca_cacheada(chave: str, resposta: RespostaBusca) -> None:
    _CACHE_BUSCA_VOOS[chave] = (time.time(), resposta)

def resolver_aeroportos_candidatos(tipo: TipoLocal, valor: str, max_candidatos: int = 3) -> list[str]:
    valor_clean = valor.strip()
    valor_upper = valor_clean.upper()

    if tipo == TipoLocal.AEROPORTO or (len(valor_clean) == 3 and valor_clean.isalpha()):
        aeroporto = getattr(Airport, valor_upper, None)
        if aeroporto is not None:
            return [valor_upper]

    valor_norm = _remover_acentos(valor_clean)
    candidatos_principais = []
    candidatos_outros = []

    for item_idx in _INDICE_AEROPORTOS_CACHE:
        codigo = item_idx.codigo_iata
        aero = item_idx.aeroporto_out

        if tipo == TipoLocal.CIDADE:
            match = item_idx.cidade_norm == valor_norm if item_idx.cidade_norm else False
        elif tipo == TipoLocal.ESTADO:
            match = (valor_norm == item_idx.estado_uf_norm) or (valor_norm == item_idx.estado_nome_norm)
        else:
            match = (codigo == valor_upper) or (item_idx.cidade_norm == valor_norm)

        if match:
            if aero.principal:
                candidatos_principais.append(codigo)
            else:
                candidatos_outros.append(codigo)

    resultado = candidatos_principais + candidatos_outros
    if not resultado and len(valor_clean) == 3 and valor_clean.isalpha():
        resultado = [valor_upper]

    return resultado[:max_candidatos]

def _executar_busca_par(req_par: RequisicaoBusca) -> tuple[str, str, RespostaBusca | None, Exception | None]:
    chave_cache = f"{req_par.origem}:{req_par.destino}:{req_par.data_partida}:{req_par.data_retorno}:{req_par.adultos}"
    cacheado = _obter_busca_cacheada(chave_cache)
    if cacheado:
        return (req_par.origem, req_par.destino, cacheado, None)

    try:
        res = buscar_voos(req_par)
        _salvar_busca_cacheada(chave_cache, res)
        return (req_par.origem, req_par.destino, res, None)
    except Exception as exc:
        return (req_par.origem, req_par.destino, None, exc)

def buscar_voos_por_local(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
    candidatos_origem = resolver_aeroportos_candidatos(requisicao.origem_tipo, requisicao.origem_valor)
    candidatos_destino = resolver_aeroportos_candidatos(requisicao.destino_tipo, requisicao.destino_valor)

    if not candidatos_origem:
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível encontrar aeroportos para a origem '{requisicao.origem_valor}'",
        )
    if not candidatos_destino:
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível encontrar aeroportos para o destino '{requisicao.destino_valor}'",
        )

    combinacoes = [(orig, dest) for orig in candidatos_origem for dest in candidatos_destino]

    requisicoes_par: list[RequisicaoBusca] = []
    for orig, dest in combinacoes:
        requisicoes_par.append(
            RequisicaoBusca(
                origem=orig,
                destino=dest,
                data_partida=requisicao.data_partida,
                data_retorno=requisicao.data_retorno,
                adultos=requisicao.adultos,
                criancas=requisicao.criancas,
                classe_cabine=requisicao.classe_cabine,
                maximo_escalas=requisicao.maximo_escalas,
                ordenar_por=requisicao.ordenar_por,
                limite_top=requisicao.limite_top,
            )
        )

    resultados_combinacoes: list[CombinacaoVooSaida] = []
    ofertas_todas: list[tuple[OfertaVooSaida, str, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(requisicoes_par), 4)) as executor:
        futures = [executor.submit(_executar_busca_par, req) for req in requisicoes_par]
        for future in concurrent.futures.as_completed(futures):
            orig, dest, res_busca, exc = future.result()
            if exc or not res_busca:
                resultados_combinacoes.append(
                    CombinacaoVooSaida(
                        origem_iata=orig,
                        destino_iata=dest,
                        preco_minimo=None,
                        sucesso=False,
                        mensagem_erro=str(exc) if exc else "sem_resultado",
                    )
                )
            else:
                menor_preco = res_busca.ofertas[0].preco if res_busca.ofertas else None
                resultados_combinacoes.append(
                    CombinacaoVooSaida(
                        origem_iata=orig,
                        destino_iata=dest,
                        preco_minimo=menor_preco,
                        sucesso=True,
                    )
                )
                for of in res_busca.ofertas:
                    ofertas_todas.append((of, orig, dest))

    ofertas_todas.sort(key=lambda item: item[0].preco)

    melhor_oferta = ofertas_todas[0][0] if ofertas_todas else None
    origem_usada = ofertas_todas[0][1] if ofertas_todas else None
    destino_usado = ofertas_todas[0][2] if ofertas_todas else None

    return RespostaBuscaPorLocal(
        origem_buscada=requisicao.origem_valor,
        destino_buscado=requisicao.destino_valor,
        data_partida=requisicao.data_partida.isoformat(),
        data_retorno=requisicao.data_retorno.isoformat() if requisicao.data_retorno else None,
        moeda=configuracoes.MOEDA_PADRAO,
        melhor_oferta=melhor_oferta,
        aeroporto_origem_usado=origem_usada,
        aeroporto_destino_usado=destino_usado,
        todas_combinacoes=resultados_combinacoes,
    )