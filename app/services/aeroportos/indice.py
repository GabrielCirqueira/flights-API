from fli.models import Airport

from app.services.aeroportos.texto import construir_aeroporto_saida, obter_nome_estado, remover_acentos


class ItemIndiceAeroporto:
    __slots__ = (
        "aeroporto_out",
        "codigo_iata",
        "codigo_iata_norm",
        "nome_norm",
        "cidade_norm",
        "estado_uf_norm",
        "estado_nome_norm",
        "pais_norm",
    )

    def __init__(self, item: Airport):
        aero = construir_aeroporto_saida(item)
        self.aeroporto_out = aero
        self.codigo_iata = item.name
        self.codigo_iata_norm = remover_acentos(item.name)
        self.nome_norm = remover_acentos(item.value)
        self.cidade_norm = remover_acentos(aero.cidade)
        self.estado_uf_norm = remover_acentos(aero.estado)
        self.estado_nome_norm = remover_acentos(obter_nome_estado(aero.estado))
        self.pais_norm = remover_acentos(aero.pais)


INDICE_AEROPORTOS: list[ItemIndiceAeroporto] = [ItemIndiceAeroporto(item) for item in Airport]
