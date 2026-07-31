import time

from app.schemas.voos import RespostaBusca

_CACHE: dict[str, tuple[float, RespostaBusca]] = {}
_TTL_SEGUNDOS = 300.0


def obter(chave: str) -> RespostaBusca | None:
    if chave in _CACHE:
        ts, resposta = _CACHE[chave]
        if time.time() - ts < _TTL_SEGUNDOS:
            return resposta
        del _CACHE[chave]
    return None


def salvar(chave: str, resposta: RespostaBusca) -> None:
    _CACHE[chave] = (time.time(), resposta)
