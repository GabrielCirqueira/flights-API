
from datetime import date
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
    data_inicio: date
    data_fim: date
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
        if self.data_fim < self.data_inicio:
            raise ValueError("data_fim não pode ser anterior a data_inicio")
        return self

class RequisicaoBuscaPorLocal(BaseModel):

    origem_tipo: TipoLocal = TipoLocal.CIDADE
    origem_valor: str = Field(..., min_length=1, description="ex: Vitória, ES ou VIX")
    destino_tipo: TipoLocal = TipoLocal.CIDADE
    destino_valor: str = Field(..., min_length=1, description="ex: São Paulo, SP ou GRU")
    data_partida: date
    data_retorno: date | None = None
    adultos: int = Field(default=1, ge=1, le=9)
    criancas: int = Field(default=0, ge=0, le=8)
    classe_cabine: str = Field(default="ECONOMY")
    maximo_escalas: str = Field(default="ANY")
    ordenar_por: str = Field(default="CHEAPEST")
    limite_top: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validar_data_retorno(self) -> "RequisicaoBuscaPorLocal":
        if self.data_retorno and self.data_retorno < self.data_partida:
            raise ValueError("data_retorno não pode ser anterior a data_partida")
        return self