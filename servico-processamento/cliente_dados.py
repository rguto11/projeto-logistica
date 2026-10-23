"""Cliente HTTP do Servico de Dados (paginacao, timeout e retentativas)."""
import os
import time

import requests

DADOS_URL = os.environ.get("DADOS_URL", "http://servico-dados:8001").rstrip("/")
# Pior caso por chamada ao Dados = TENTATIVAS x HTTP_TIMEOUT + ESPERA_S ~ 11 s;
# o Relatorio espera mais que isso (HTTP_TIMEOUT=30 s), entao a falha e reportada aqui.
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "5"))
TENTATIVAS = 2
ESPERA_S = 1
PAGINA = 1000

_sessao = requests.Session()


class DadosIndisponivel(Exception):
    """Servico de Dados fora do ar, lento ou com resposta inesperada (-> HTTP 502)."""


class ParametroInvalido(Exception):
    """O Servico de Dados rejeitou os filtros enviados (-> HTTP 400)."""


def _get(caminho, params):
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resp = _sessao.get(f"{DADOS_URL}{caminho}", params=params, timeout=HTTP_TIMEOUT)
            if resp.status_code == 400:
                raise ParametroInvalido(resp.json().get("erro", "parametros invalidos"))
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except ParametroInvalido:
            raise
        except (requests.RequestException, ValueError) as exc:
            ultimo_erro = exc
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_S)
    raise DadosIndisponivel(str(ultimo_erro))


def listar_todas(recurso, params=None):
    """Percorre todas as paginas de /<recurso> e devolve a lista completa de itens."""
    filtros = dict(params or {})
    itens, offset = [], 0
    while True:
        pagina = _get(f"/{recurso}", {**filtros, "limit": PAGINA, "offset": offset})
        lote = pagina["itens"]
        itens.extend(lote)
        offset += PAGINA
        if len(lote) < PAGINA or offset >= pagina["total"]:
            return itens
