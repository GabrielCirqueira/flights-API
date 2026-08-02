from datetime import date, timedelta

from app.core.config import configuracoes


def resolver_intervalo_janela(
    data_inicio: date | None,
    data_fim: date | None,
    janela_dias: int | None = None,
) -> tuple[date, date, int, bool]:
    hoje = date.today()
    dias = janela_dias or configuracoes.JANELA_BUSCA_ABERTA_DIAS
    aberta = data_inicio is None and data_fim is None

    if data_inicio is None and data_fim is None:
        inicio = hoje
        fim = hoje + timedelta(days=dias)
    elif data_inicio is not None and data_fim is None:
        inicio = data_inicio
        fim = data_inicio + timedelta(days=dias)
    elif data_inicio is None and data_fim is not None:
        inicio = hoje
        fim = data_fim
    else:
        inicio = data_inicio  # type: ignore[assignment]
        fim = data_fim  # type: ignore[assignment]

    if fim < inicio:
        raise ValueError("data_fim não pode ser anterior a data_inicio")
    if inicio < hoje and aberta:
        inicio = hoje

    return inicio, fim, dias, aberta
