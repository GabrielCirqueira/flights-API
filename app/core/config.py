
import os


_ORIGENS_DEV = [
    "http://127.0.0.1:8010",
    "http://localhost:8010",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def _carregar_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    extras = [origem.strip().rstrip("/") for origem in raw.split(",") if origem.strip()]
    vistas: set[str] = set()
    resultado: list[str] = []
    for origem in _ORIGENS_DEV + extras:
        if origem not in vistas:
            vistas.add(origem)
            resultado.append(origem)
    return resultado


class Configuracoes:
    NOME_SERVICO: str = "voobarato-flights-api"
    VERSAO_SERVICO: str = "1.0.0"

    IDIOMA_PADRAO: str = os.getenv("FLIGHTS_LANGUAGE", "pt-BR")
    PAIS_PADRAO: str = os.getenv("FLIGHTS_COUNTRY", "BR")
    MOEDA_PADRAO: str = os.getenv("FLIGHTS_CURRENCY", "BRL")

    TIMEOUT_REQUISICAO_SEGUNDOS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))

    JANELA_BUSCA_ABERTA_DIAS: int = int(os.getenv("OPEN_SEARCH_WINDOW_DAYS", "90"))

    TOKEN_INTERNO: str | None = os.getenv("FLIGHTS_API_INTERNAL_TOKEN")

    CORS_ORIGINS: list[str] = _carregar_cors_origins()


configuracoes = Configuracoes()
