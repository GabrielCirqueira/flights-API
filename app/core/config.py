
import os


class Configuracoes:
    NOME_SERVICO: str = "voobarato-flights-api"
    VERSAO_SERVICO: str = "1.0.0"

    IDIOMA_PADRAO: str = os.getenv("FLIGHTS_LANGUAGE", "pt-BR")
    PAIS_PADRAO: str = os.getenv("FLIGHTS_COUNTRY", "BR")
    MOEDA_PADRAO: str = os.getenv("FLIGHTS_CURRENCY", "BRL")

    TIMEOUT_REQUISICAO_SEGUNDOS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))

    TOKEN_INTERNO: str | None = os.getenv("FLIGHTS_API_INTERNAL_TOKEN")

configuracoes = Configuracoes()
