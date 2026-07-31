import concurrent.futures

from fastapi import HTTPException

from app.core.config import configuracoes
from app.schemas.voos import (
    CombinacaoVooSaida,
    OfertaVooSaida,
    RequisicaoBusca,
    RequisicaoBuscaPorLocal,
    RespostaBusca,
    RespostaBuscaPorLocal,
)
from app.services.aeroportos.resolucao import resolver_aeroportos_candidatos
from app.services.voos import cache as cache_voos
from app.services.voos.busca import buscar_voos


def _executar_busca_par(req_par: RequisicaoBusca) -> tuple[str, str, RespostaBusca | None, Exception | None]:
    chave_cache = f"{req_par.origem}:{req_par.destino}:{req_par.data_partida}:{req_par.data_retorno}:{req_par.adultos}"
    cacheado = cache_voos.obter(chave_cache)
    if cacheado:
        return (req_par.origem, req_par.destino, cacheado, None)

    try:
        res = buscar_voos(req_par)
        cache_voos.salvar(chave_cache, res)
        return (req_par.origem, req_par.destino, res, None)
    except Exception as exc:
        return (req_par.origem, req_par.destino, None, exc)


def buscar_voos_por_local(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
    candidatos_origem = resolver_aeroportos_candidatos(requisicao.origem_tipo, requisicao.origem_valor)
    candidatos_destino = resolver_aeroportos_candidatos(requisicao.destino_tipo, requisicao.destino_valor)

    if not candidatos_origem:
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível encontrar aeroportos para a origem '{requisicao.origem_valor}'",
        )
    if not candidatos_destino:
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível encontrar aeroportos para o destino '{requisicao.destino_valor}'",
        )

    combinacoes = [(orig, dest) for orig in candidatos_origem for dest in candidatos_destino]

    requisicoes_par: list[RequisicaoBusca] = []
    for orig, dest in combinacoes:
        requisicoes_par.append(
            RequisicaoBusca(
                origem=orig,
                destino=dest,
                data_partida=requisicao.data_partida,
                data_retorno=requisicao.data_retorno,
                adultos=requisicao.adultos,
                criancas=requisicao.criancas,
                classe_cabine=requisicao.classe_cabine,
                maximo_escalas=requisicao.maximo_escalas,
                ordenar_por=requisicao.ordenar_por,
                limite_top=requisicao.limite_top,
            )
        )

    resultados_combinacoes: list[CombinacaoVooSaida] = []
    ofertas_todas: list[tuple[OfertaVooSaida, str, str]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(requisicoes_par), 4)) as executor:
        futures = [executor.submit(_executar_busca_par, req) for req in requisicoes_par]
        for future in concurrent.futures.as_completed(futures):
            orig, dest, res_busca, exc = future.result()
            if exc or not res_busca:
                resultados_combinacoes.append(
                    CombinacaoVooSaida(
                        origem_iata=orig,
                        destino_iata=dest,
                        preco_minimo=None,
                        sucesso=False,
                        mensagem_erro=str(exc) if exc else "sem_resultado",
                    )
                )
            else:
                menor_preco = res_busca.ofertas[0].preco if res_busca.ofertas else None
                resultados_combinacoes.append(
                    CombinacaoVooSaida(
                        origem_iata=orig,
                        destino_iata=dest,
                        preco_minimo=menor_preco,
                        sucesso=True,
                    )
                )
                for of in res_busca.ofertas:
                    ofertas_todas.append((of, orig, dest))

    ofertas_todas.sort(key=lambda item: item[0].preco)

    melhor_oferta = ofertas_todas[0][0] if ofertas_todas else None
    origem_usada = ofertas_todas[0][1] if ofertas_todas else None
    destino_usado = ofertas_todas[0][2] if ofertas_todas else None

    return RespostaBuscaPorLocal(
        origem_buscada=requisicao.origem_valor,
        destino_buscado=requisicao.destino_valor,
        data_partida=requisicao.data_partida.isoformat(),
        data_retorno=requisicao.data_retorno.isoformat() if requisicao.data_retorno else None,
        moeda=configuracoes.MOEDA_PADRAO,
        melhor_oferta=melhor_oferta,
        aeroporto_origem_usado=origem_usada,
        aeroporto_destino_usado=destino_usado,
        todas_combinacoes=resultados_combinacoes,
    )
