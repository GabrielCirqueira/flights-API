from fastapi import HTTPException
from fli.models import Airport

from app.schemas.aeroportos import AeroportoSaida, RespostaListaAeroportos
from app.services.aeroportos.indice import INDICE_AEROPORTOS
from app.services.aeroportos.texto import construir_aeroporto_saida, remover_acentos


def listar_aeroportos(
    busca: str | None = None,
    cidade: str | None = None,
    estado: str | None = None,
    pais: str | None = None,
    apenas_principais: bool = False,
    limite: int = 20,
) -> RespostaListaAeroportos:
    termo_norm = remover_acentos(busca)
    termo_upper = busca.strip().upper() if busca else ""
    cidade_norm = remover_acentos(cidade)
    estado_norm = remover_acentos(estado)
    pais_norm = remover_acentos(pais)

    exatos_cidade_principal = []
    prefixos_cidade_principal = []
    outros_principais = []
    exatos_iata = []
    inicio_iata = []
    outros_match = []

    for item_idx in INDICE_AEROPORTOS:
        aero_out = item_idx.aeroporto_out

        if apenas_principais and not aero_out.principal:
            continue

        if cidade_norm and cidade_norm != item_idx.cidade_norm:
            continue

        if estado_norm:
            if estado_norm != item_idx.estado_uf_norm and estado_norm != item_idx.estado_nome_norm:
                continue

        if pais_norm and pais_norm != item_idx.pais_norm:
            continue

        if not termo_norm:
            outros_match.append(aero_out)
            continue

        cidade_aero_norm = item_idx.cidade_norm
        nome_aero_norm = item_idx.nome_norm
        codigo = item_idx.codigo_iata

        match_cidade_exata = (cidade_aero_norm == termo_norm) if cidade_aero_norm else False
        match_cidade_inicio = (cidade_aero_norm.startswith(termo_norm)) if cidade_aero_norm else False
        match_cidade_contem = (termo_norm in cidade_aero_norm) if cidade_aero_norm else False
        match_estado_exato = (termo_norm == item_idx.estado_uf_norm) or (termo_norm == item_idx.estado_nome_norm)
        match_nome = termo_norm in nome_aero_norm
        match_iata = codigo == termo_upper
        match_inicio_iata = codigo.startswith(termo_upper)

        if aero_out.principal and (match_cidade_exata or match_iata or match_estado_exato):
            exatos_cidade_principal.append(aero_out)
        elif aero_out.principal and match_cidade_inicio:
            prefixos_cidade_principal.append(aero_out)
        elif aero_out.principal and (match_cidade_contem or match_nome):
            outros_principais.append(aero_out)
        elif match_iata:
            exatos_iata.append(aero_out)
        elif match_inicio_iata:
            inicio_iata.append(aero_out)
        elif match_cidade_contem or match_estado_exato or match_nome:
            outros_match.append(aero_out)

    todos = (
        exatos_cidade_principal
        + prefixos_cidade_principal
        + outros_principais
        + exatos_iata
        + inicio_iata
        + outros_match
    )
    return RespostaListaAeroportos(total=len(todos), aeroportos=todos[:limite])


def obter_aeroporto_por_codigo(codigo_iata: str) -> AeroportoSaida:
    codigo = codigo_iata.strip().upper()
    aeroporto = getattr(Airport, codigo, None)
    if aeroporto is None:
        raise HTTPException(
            status_code=404,
            detail=f"Aeroporto com código IATA '{codigo}' não encontrado.",
        )
    return construir_aeroporto_saida(aeroporto)
