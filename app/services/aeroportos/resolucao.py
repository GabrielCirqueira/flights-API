from fli.models import Airport

from app.schemas.voos import TipoLocal
from app.services.aeroportos.indice import INDICE_AEROPORTOS
from app.services.aeroportos.texto import remover_acentos


def resolver_aeroportos_candidatos(tipo: TipoLocal, valor: str, max_candidatos: int = 3) -> list[str]:
    valor_clean = valor.strip()
    valor_upper = valor_clean.upper()

    if tipo == TipoLocal.AEROPORTO or (len(valor_clean) == 3 and valor_clean.isalpha()):
        aeroporto = getattr(Airport, valor_upper, None)
        if aeroporto is not None:
            return [valor_upper]

    valor_norm = remover_acentos(valor_clean)
    candidatos_principais = []
    candidatos_outros = []

    for item_idx in INDICE_AEROPORTOS:
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
