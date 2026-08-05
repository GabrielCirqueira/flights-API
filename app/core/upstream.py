import logging
import os

from app.core.config import configuracoes

logger = logging.getLogger("flights_api.upstream")


def configurar_upstream() -> None:
    os.environ["FLI_TIMEOUT"] = str(configuracoes.TIMEOUT_REQUISICAO_SEGUNDOS)

    if configuracoes.PROXY_HTTPS:
        os.environ["HTTPS_PROXY"] = configuracoes.PROXY_HTTPS
        os.environ["HTTP_PROXY"] = configuracoes.PROXY_HTTPS
        logger.info("Proxy HTTPS configurado para requisições upstream (Google Flights)")
    else:
        logger.warning(
            "Nenhum proxy HTTPS configurado — em datacenters o Google Flights "
            "pode retornar zero ofertas. Defina FLIGHTS_HTTPS_PROXY ou HTTPS_PROXY."
        )
