from pydantic import BaseModel, Field


class CidadeSaida(BaseModel):
    nome: str = Field(description="Nome da cidade (ex: São Paulo, Goiânia)")
    estado: str | None = Field(default=None, description="Sigla do estado / UF (ex: SP, GO)")
    estado_nome: str | None = Field(default=None, description="Nome por extenso do estado (ex: São Paulo, Goiás)")
    pais: str = Field(default="Brasil", description="País da cidade (ex: Brasil)")


class RespostaListaCidades(BaseModel):
    total: int
    cidades: list[CidadeSaida]
