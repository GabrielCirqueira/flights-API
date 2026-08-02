import concurrent.futures
import logging

from fastapi import HTTPException

from app.core.config import configuracoes
from app.schemas.voos import (
    CombinacaoVooSaida,
    DataPrecoPorLocalSaida,
    DataPrecoSaida,
    OfertaBuscaPorLocalSaida,
    RequisicaoBusca,
    RequisicaoBuscaAberta,
    RequisicaoBuscaPorLocal,
    RespostaBusca,
    RespostaBuscaPorLocal,
)
from app.services.aeroportos.resolucao import resolver_aeroportos_candidatos
from app.services.voos import cache as cache_voos
from app.services.voos.busca import buscar_voos
from app.services.voos.busca_janela import _buscar_precos_por_dia, _expandir_melhores_datas
from app.services.voos.janela_util import resolver_intervalo_janela

logger = logging.getLogger("flights_api.voos.busca_por_local")


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


def _expandir_oferta_data(
    dp: DataPrecoPorLocalSaida,
    adultos: int,
    classe_cabine: str,
    maximo_escalas: str,
) -> OfertaBuscaPorLocalSaida | None:
    expandidas = _expandir_melhores_datas(
        dp.aeroporto_origem_iata,
        dp.aeroporto_destino_iata,
        [DataPrecoSaida(data=dp.data, preco=dp.preco, moeda=dp.moeda)],
        1,
        adultos,
        classe_cabine,
        maximo_escalas,
    )
    if not expandidas:
        return None
    return OfertaBuscaPorLocalSaida(
        **expandidas[0].model_dump(),
        aeroporto_origem_iata=dp.aeroporto_origem_iata,
        aeroporto_destino_iata=dp.aeroporto_destino_iata,
    )


def _limite_expansao(expandir_top: int | None, total_datas: int) -> int:
    if expandir_top == 0:
        return 0
    if expandir_top is None:
        return total_datas
    return min(expandir_top, total_datas)


def _buscar_por_local_aberta(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
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

    try:
        inicio, fim, dias, _ = resolver_intervalo_janela(None, None, requisicao.janela_dias)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    combinacoes = [(orig, dest) for orig in candidatos_origem for dest in candidatos_destino]
    resultados_combinacoes: list[CombinacaoVooSaida] = []
    por_data_map: dict[str, DataPrecoPorLocalSaida] = {}

    def _janela_par(orig: str, dest: str) -> tuple[str, str, list, Exception | None]:
        try:
            precos = _buscar_precos_por_dia(
                orig,
                dest,
                inicio,
                fim,
                requisicao.adultos,
                requisicao.classe_cabine,
                requisicao.maximo_escalas,
            )
            return orig, dest, precos, None
        except Exception as exc:
            return orig, dest, [], exc

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(combinacoes), 4)) as executor:
        futures = [executor.submit(_janela_par, orig, dest) for orig, dest in combinacoes]
        for future in concurrent.futures.as_completed(futures):
            orig, dest, precos, exc = future.result()
            if exc or not precos:
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
                resultados_combinacoes.append(
                    CombinacaoVooSaida(
                        origem_iata=orig,
                        destino_iata=dest,
                        preco_minimo=precos[0].preco,
                        sucesso=True,
                    )
                )
                for dp in precos:
                    existente = por_data_map.get(dp.data)
                    if existente is None or dp.preco < existente.preco:
                        por_data_map[dp.data] = DataPrecoPorLocalSaida(
                            data=dp.data,
                            preco=dp.preco,
                            moeda=dp.moeda,
                            aeroporto_origem_iata=orig,
                            aeroporto_destino_iata=dest,
                        )

    por_data = sorted(por_data_map.values(), key=lambda item: item.preco)

    limite = _limite_expansao(requisicao.expandir_top, len(por_data))
    datas_expandir = por_data[:limite] if limite > 0 else []

    oferta_por_data: dict[str, OfertaBuscaPorLocalSaida] = {}
    if datas_expandir:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(datas_expandir), 4)) as executor:
            futures = {
                executor.submit(
                    _expandir_oferta_data,
                    dp,
                    requisicao.adultos,
                    requisicao.classe_cabine,
                    requisicao.maximo_escalas,
                ): dp
                for dp in datas_expandir
            }
            for future in concurrent.futures.as_completed(futures):
                dp = futures[future]
                oferta = future.result()
                if oferta:
                    oferta_por_data[dp.data] = oferta

    por_data_completo: list[DataPrecoPorLocalSaida] = []
    ofertas_todas: list[OfertaBuscaPorLocalSaida] = []
    for dp in por_data:
        oferta = oferta_por_data.get(dp.data)
        por_data_completo.append(
            DataPrecoPorLocalSaida(
                data=dp.data,
                preco=dp.preco,
                moeda=dp.moeda,
                aeroporto_origem_iata=dp.aeroporto_origem_iata,
                aeroporto_destino_iata=dp.aeroporto_destino_iata,
                oferta=oferta,
            )
        )
        if oferta:
            ofertas_todas.append(oferta)

    ofertas_todas.sort(key=lambda item: item.preco)
    melhor = ofertas_todas[0] if ofertas_todas else None

    return RespostaBuscaPorLocal(
        origem_buscada=requisicao.origem_valor,
        destino_buscado=requisicao.destino_valor,
        modo_busca="aberta",
        data_inicio=inicio.isoformat(),
        data_fim=fim.isoformat(),
        janela_dias=dias,
        moeda=configuracoes.MOEDA_PADRAO,
        por_data=por_data_completo,
        ofertas=ofertas_todas,
        total=len(ofertas_todas),
        melhor_oferta=melhor,
        aeroporto_origem_usado=melhor.aeroporto_origem_iata if melhor else None,
        aeroporto_destino_usado=melhor.aeroporto_destino_iata if melhor else None,
        todas_combinacoes=resultados_combinacoes,
    )


def buscar_voos_por_local(requisicao: RequisicaoBuscaPorLocal) -> RespostaBuscaPorLocal:
    if requisicao.data_partida is None:
        return _buscar_por_local_aberta(requisicao)

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
    ofertas_todas: list[OfertaBuscaPorLocalSaida] = []

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
                    ofertas_todas.append(
                        OfertaBuscaPorLocalSaida(
                            **of.model_dump(),
                            aeroporto_origem_iata=orig,
                            aeroporto_destino_iata=dest,
                        )
                    )

    ofertas_todas.sort(key=lambda item: item.preco)

    melhor = ofertas_todas[0] if ofertas_todas else None

    return RespostaBuscaPorLocal(
        origem_buscada=requisicao.origem_valor,
        destino_buscado=requisicao.destino_valor,
        modo_busca="data_fixa",
        data_partida=requisicao.data_partida.isoformat(),
        data_retorno=requisicao.data_retorno.isoformat() if requisicao.data_retorno else None,
        moeda=configuracoes.MOEDA_PADRAO,
        ofertas=ofertas_todas,
        total=len(ofertas_todas),
        melhor_oferta=melhor,
        aeroporto_origem_usado=melhor.aeroporto_origem_iata if melhor else None,
        aeroporto_destino_usado=melhor.aeroporto_destino_iata if melhor else None,
        todas_combinacoes=resultados_combinacoes,
    )


def buscar_aberta(requisicao: RequisicaoBuscaAberta) -> RespostaBuscaPorLocal:
    return buscar_voos_por_local(
        RequisicaoBuscaPorLocal(
            origem_tipo=requisicao.origem_tipo,
            origem_valor=requisicao.origem_valor,
            destino_tipo=requisicao.destino_tipo,
            destino_valor=requisicao.destino_valor,
            janela_dias=requisicao.janela_dias,
            expandir_top=requisicao.expandir_top,
            adultos=requisicao.adultos,
            classe_cabine=requisicao.classe_cabine,
            maximo_escalas=requisicao.maximo_escalas,
        )
    )
