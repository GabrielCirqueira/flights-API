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
