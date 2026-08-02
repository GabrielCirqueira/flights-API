from app.schemas.cidades import CidadeSaida, RespostaListaCidades
from app.services.aeroportos.indice import INDICE_AEROPORTOS
from app.services.aeroportos.texto import obter_nome_estado, remover_acentos


class ItemIndiceCidade:
    __slots__ = (
        "cidade_out",
        "cidade_norm",
        "estado_uf_norm",
        "estado_nome_norm",
        "pais_norm",
    )

    def __init__(self, nome: str, estado: str | None, pais: str | None):
        estado_nome = obter_nome_estado(estado) if estado else None
        self.cidade_out = CidadeSaida(
            nome=nome,
            estado=estado,
            estado_nome=estado_nome,
            pais=pais or "Brasil",
        )
        self.cidade_norm = remover_acentos(nome)
        self.estado_uf_norm = remover_acentos(estado) if estado else ""
        self.estado_nome_norm = remover_acentos(estado_nome) if estado_nome else ""
        self.pais_norm = remover_acentos(pais) if pais else ""


def _construir_indice_cidades() -> list[ItemIndiceCidade]:
    cidades_vistas: set[tuple[str, str | None, str | None]] = set()
    indice: list[ItemIndiceCidade] = []

    for item in INDICE_AEROPORTOS:
        aero = item.aeroporto_out
        if not aero.cidade:
            continue
        chave = (aero.cidade, aero.estado, aero.pais)
        if chave not in cidades_vistas:
            cidades_vistas.add(chave)
            indice.append(ItemIndiceCidade(aero.cidade, aero.estado, aero.pais))

    indice.sort(key=lambda x: x.cidade_norm)
    return indice


INDICE_CIDADES: list[ItemIndiceCidade] = _construir_indice_cidades()


def listar_cidades(
    busca: str | None = None,
    estado: str | None = None,
    pais: str | None = None,
    limite: int = 20,
) -> RespostaListaCidades:
    termo_norm = remover_acentos(busca)
    estado_norm = remover_acentos(estado)
    pais_norm = remover_acentos(pais)

    exatos = []
    prefixos = []
    outros = []

    for item in INDICE_CIDADES:
        cidade_out = item.cidade_out

        if estado_norm:
            if estado_norm != item.estado_uf_norm and estado_norm != item.estado_nome_norm:
                continue

        if pais_norm and pais_norm != item.pais_norm:
            continue

        if not termo_norm:
            outros.append(cidade_out)
            continue

        match_exato = (item.cidade_norm == termo_norm) or (item.estado_uf_norm == termo_norm)
        match_inicio = item.cidade_norm.startswith(termo_norm)
        match_contem = (
            (termo_norm in item.cidade_norm)
            or (termo_norm in item.estado_nome_norm)
            or (termo_norm in item.estado_uf_norm)
        )

        if match_exato:
            exatos.append(cidade_out)
        elif match_inicio:
            prefixos.append(cidade_out)
        elif match_contem:
            outros.append(cidade_out)

    resultados = exatos + prefixos + outros
    return RespostaListaCidades(total=len(resultados), cidades=resultados[:limite])
