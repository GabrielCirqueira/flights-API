from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

TAMANHO_IATA = 3


class TipoLocal(str, Enum):
    AEROPORTO = "aeroporto"
    CIDADE = "cidade"
    ESTADO = "estado"


class RequisicaoBusca(BaseModel):
    origem: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    destino: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    data_partida: date
    data_retorno: date | None = None
    adultos: int = Field(default=1, ge=1, le=9)
    criancas: int = Field(default=0, ge=0, le=8)
    classe_cabine: str = Field(default="ECONOMY")
    maximo_escalas: str = Field(default="ANY")
    ordenar_por: str = Field(default="CHEAPEST")
    limite_top: int = Field(default=10, ge=1, le=50)

    @field_validator("origem", "destino")
    @classmethod
    def validar_e_formatar_iata(cls, v: str) -> str:
        v = v.upper().strip()
        if not v.isalpha():
            raise ValueError("código IATA deve ter 3 letras (ex: GRU)")
        return v

    @model_validator(mode="after")
    def validar_data_retorno(self) -> "RequisicaoBusca":
        if self.data_retorno and self.data_retorno < self.data_partida:
            raise ValueError("data_retorno não pode ser anterior a data_partida")
        return self


class RequisicaoBuscaJanela(BaseModel):
    origem: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    destino: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    data_inicio: date | None = None
    data_fim: date | None = None
    janela_dias: int | None = Field(default=None, ge=1, le=180)
    adultos: int = Field(default=1, ge=1, le=9)
    classe_cabine: str = Field(default="ECONOMY")
    maximo_escalas: str = Field(default="ANY")
    expandir_top: int = Field(default=1, ge=0, le=10)

    @field_validator("origem", "destino")
    @classmethod
    def validar_e_formatar_iata(cls, v: str) -> str:
        v = v.upper().strip()
        if not v.isalpha():
            raise ValueError("código IATA deve ter 3 letras (ex: GRU)")
        return v

    @model_validator(mode="after")
    def validar_intervalo_datas(self) -> "RequisicaoBuscaJanela":
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValueError("data_fim não pode ser anterior a data_inicio")
        if self.data_fim and not self.data_inicio and self.data_fim < date.today():
            raise ValueError("data_fim não pode ser anterior a hoje")
        return self


class RequisicaoBuscaAberta(BaseModel):
    origem: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    destino: str = Field(..., min_length=TAMANHO_IATA, max_length=TAMANHO_IATA)
    janela_dias: int | None = Field(default=None, ge=1, le=180)
    adultos: int = Field(default=1, ge=1, le=9)
    classe_cabine: str = Field(default="ECONOMY")
    maximo_escalas: str = Field(default="ANY")
    expandir_top: int = Field(default=5, ge=0, le=10)

    @field_validator("origem", "destino")
    @classmethod
    def validar_e_formatar_iata(cls, v: str) -> str:
        v = v.upper().strip()
        if not v.isalpha():
            raise ValueError("código IATA deve ter 3 letras (ex: GRU)")
        return v


class RequisicaoBuscaPorLocal(BaseModel):
    origem_tipo: TipoLocal = TipoLocal.CIDADE
    origem_valor: str = Field(..., min_length=1, description="ex: Vitória, ES ou VIX")
    destino_tipo: TipoLocal = TipoLocal.CIDADE
    destino_valor: str = Field(..., min_length=1, description="ex: São Paulo, SP ou GRU")
    data_partida: date | None = None
    data_retorno: date | None = None
    janela_dias: int | None = Field(default=None, ge=1, le=180)
    expandir_top: int = Field(default=5, ge=0, le=10)
    adultos: int = Field(default=1, ge=1, le=9)
    criancas: int = Field(default=0, ge=0, le=8)
    classe_cabine: str = Field(default="ECONOMY")
    maximo_escalas: str = Field(default="ANY")
    ordenar_por: str = Field(default="CHEAPEST")
    limite_top: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validar_datas(self) -> "RequisicaoBuscaPorLocal":
        if self.data_retorno and not self.data_partida:
            raise ValueError("data_retorno exige data_partida")
        if self.data_retorno and self.data_partida and self.data_retorno < self.data_partida:
            raise ValueError("data_retorno não pode ser anterior a data_partida")
        return self


class TrechoVooSaida(BaseModel):
    iata_partida: str
    iata_chegada: str
    aeroporto_partida: str
    aeroporto_chegada: str
    companhia_aerea: str
    nome_companhia_aerea: str | None = None
    numero_voo: str | None = None
    data_hora_partida: datetime
    data_hora_chegada: datetime
    duracao_minutos: int | None = None
    aeronave: str | None = None
    companhia_operadora: str | None = None


class ParadaRotaSaida(BaseModel):
    iata: str
    cidade: str | None = None


class OfertaVooSaida(BaseModel):
    preco: float
    moeda: str
    duracao_minutos: int
    escalas: int
    direto: bool
    com_conexao: bool
    rota_iata: list[ParadaRotaSaida]
    aeroportos_conexao: list[ParadaRotaSaida]
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


class DataPrecoPorLocalSaida(DataPrecoSaida):
    aeroporto_origem_iata: str
    aeroporto_destino_iata: str


class RespostaBuscaJanela(BaseModel):
    origem: str
    destino: str
    data_inicio: str
    data_fim: str
    moeda: str
    modo_busca: str
    janela_dias: int | None = None
    por_data: list[DataPrecoSaida]
    mais_baratas_expandidas: list[OfertaVooSaida]


class CombinacaoVooSaida(BaseModel):
    origem_iata: str
    destino_iata: str
    preco_minimo: float | None = None
    sucesso: bool = True
    mensagem_erro: str | None = None


class OfertaBuscaPorLocalSaida(OfertaVooSaida):
    aeroporto_origem_iata: str
    aeroporto_destino_iata: str


class RespostaBuscaPorLocal(BaseModel):
    origem_buscada: str
    destino_buscado: str
    modo_busca: str
    data_partida: str | None = None
    data_retorno: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    janela_dias: int | None = None
    moeda: str
    por_data: list[DataPrecoPorLocalSaida] = Field(default_factory=list)
    ofertas: list[OfertaBuscaPorLocalSaida]
    total: int
    melhor_oferta: OfertaVooSaida | None = None
    aeroporto_origem_usado: str | None = None
    aeroporto_destino_usado: str | None = None
    todas_combinacoes: list[CombinacaoVooSaida]
