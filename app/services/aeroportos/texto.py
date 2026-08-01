import unicodedata

from fli.models import Airport

from app.schemas.aeroportos import AeroportoSaida
from app.services.aeroportos.dados import ESTADOS_BRASIL, MAPEAMENTO_AEROPORTOS


def remover_acentos(texto: str | None) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


def obter_nome_estado(sigla_ou_nome: str | None) -> str:
    if not sigla_ou_nome:
        return ""
    sigla = sigla_ou_nome.strip().upper()
    return ESTADOS_BRASIL.get(sigla, sigla_ou_nome)


def construir_aeroporto_saida(item: Airport) -> AeroportoSaida:
    codigo = item.name
    nome = item.value
    info = MAPEAMENTO_AEROPORTOS.get(codigo)
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


def obter_cidade_por_iata(iata: str) -> str | None:
    codigo = iata.strip().upper()
    info = MAPEAMENTO_AEROPORTOS.get(codigo)
    if info:
        return info[0]
    aeroporto = getattr(Airport, codigo, None)
    if aeroporto is not None:
        return construir_aeroporto_saida(aeroporto).cidade
    return None
