
from datetime import datetime

from pydantic import BaseModel

class AeroportoSaida(BaseModel):
    codigo_iata: str
    nome: str
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    principal: bool = False
    descricao_curta: str | None = None

class RespostaListaAeroportos(BaseModel):
    total: int
    aeroportos: list[AeroportoSaida]

class TrechoVooSaida(BaseModel):
    companhia_aerea: str
    nome_companhia_aerea: str | None = None
    numero_voo: str | None = None
    aeroporto_partida: str
    aeroporto_chegada: str
    data_hora_partida: datetime
    data_hora_chegada: datetime
    duracao_minutos: int | None = None
    aeronave: str | None = None
    companhia_operadora: str | None = None

class OfertaVooSaida(BaseModel):

    preco: float
    moeda: str
    duracao_minutos: int
    escalas: int
    companhia_principal: str
    nome_companhia_principal: str | None = None
    trechos: list[TrechoVooSaida]
    url_busca_google_flights: str
    encontrado_em: datetime
    fonte: str = "fli"

class RespostaBusca(BaseModel):
    origem: str
    destino: str
    data_partida: str
    data_retorno: str | None = None
    moeda: str
    ofertas: list[OfertaVooSaida]
    total: int

class DataPrecoSaida(BaseModel):
    data: str
    preco: float
    moeda: str

class RespostaBuscaJanela(BaseModel):

    origem: str
    destino: str
    data_inicio: str
    data_fim: str
    moeda: str
    por_data: list[DataPrecoSaida]
    mais_baratas_expandidas: list[OfertaVooSaida]

class CombinacaoVooSaida(BaseModel):
    origem_iata: str
    destino_iata: str
    preco_minimo: float | None = None
    sucesso: bool = True
    mensagem_erro: str | None = None

class RespostaBuscaPorLocal(BaseModel):

    origem_buscada: str
    destino_buscado: str
    data_partida: str
    data_retorno: str | None = None
    moeda: str
    melhor_oferta: OfertaVooSaida | None = None
    aeroporto_origem_usado: str | None = None
    aeroporto_destino_usado: str | None = None
    todas_combinacoes: list[CombinacaoVooSaida]