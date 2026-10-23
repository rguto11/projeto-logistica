"""Testes do cliente HTTP do Servico de Dados (sem rede: a sessao e simulada)."""
import pytest
import requests

import cliente_dados


class FakeResp:
    def __init__(self, status_code, payload=None, json_invalido=False):
        self.status_code = status_code
        self._payload = payload
        self._json_invalido = json_invalido

    def json(self):
        if self._json_invalido:
            raise ValueError("json invalido")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """Registra as pausas entre tentativas em vez de dormir de verdade."""
    pausas = []
    monkeypatch.setattr(cliente_dados.time, "sleep", pausas.append)
    return pausas


def instalar_get(monkeypatch, respostas):
    """Troca _sessao.get por uma funcao que devolve/levanta os itens de 'respostas' em ordem."""
    chamadas = []
    fila = list(respostas)

    def fake_get(url, params=None, timeout=None):
        chamadas.append({"url": url, "params": params, "timeout": timeout})
        item = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(cliente_dados._sessao, "get", fake_get)
    return chamadas


def test_listar_todas_percorre_duas_paginas(monkeypatch):
    monkeypatch.setattr(cliente_dados, "PAGINA", 2)
    chamadas = []

    def fake_get(url, params=None, timeout=None):
        chamadas.append(params)
        if params["offset"] == 0:
            return FakeResp(200, {"total": 3, "itens": [1, 2]})
        return FakeResp(200, {"total": 3, "itens": [3]})

    monkeypatch.setattr(cliente_dados._sessao, "get", fake_get)

    assert cliente_dados.listar_todas("entregas", {"regiao": "Centro"}) == [1, 2, 3]
    assert [c["offset"] for c in chamadas] == [0, 2]
    assert all(c["limit"] == 2 and c["regiao"] == "Centro" for c in chamadas)


def test_listar_todas_pagina_unica_faz_uma_chamada(monkeypatch):
    chamadas = instalar_get(monkeypatch, [FakeResp(200, {"total": 2, "itens": [1, 2]})])
    assert cliente_dados.listar_todas("motoristas") == [1, 2]
    assert len(chamadas) == 1
    assert chamadas[0]["url"].endswith("/motoristas")
    assert chamadas[0]["timeout"] == cliente_dados.HTTP_TIMEOUT


def test_400_vira_parametro_invalido_sem_retentativa(monkeypatch):
    chamadas = instalar_get(monkeypatch, [FakeResp(400, {"erro": "x"})])
    with pytest.raises(cliente_dados.ParametroInvalido, match="x"):
        cliente_dados.listar_todas("entregas")
    assert len(chamadas) == 1


def test_5xx_esgota_tentativas_e_vira_dados_indisponivel(monkeypatch, sem_espera):
    chamadas = instalar_get(monkeypatch, [FakeResp(500, {})])
    with pytest.raises(cliente_dados.DadosIndisponivel):
        cliente_dados.listar_todas("entregas")
    assert len(chamadas) == cliente_dados.TENTATIVAS
    assert len(sem_espera) == cliente_dados.TENTATIVAS - 1


def test_5xx_seguido_de_sucesso_recupera(monkeypatch):
    chamadas = instalar_get(monkeypatch, [FakeResp(500, {}), FakeResp(200, {"total": 1, "itens": [7]})])
    assert cliente_dados.listar_todas("entregas") == [7]
    assert len(chamadas) == 2


def test_erro_de_conexao_vira_dados_indisponivel(monkeypatch):
    instalar_get(monkeypatch, [requests.ConnectionError("recusada")])
    with pytest.raises(cliente_dados.DadosIndisponivel, match="recusada"):
        cliente_dados.listar_todas("entregas")


@pytest.mark.parametrize("resposta", [FakeResp(404, {}), FakeResp(200, json_invalido=True)])
def test_404_e_json_invalido_viram_dados_indisponivel(monkeypatch, resposta):
    instalar_get(monkeypatch, [resposta])
    with pytest.raises(cliente_dados.DadosIndisponivel):
        cliente_dados.listar_todas("entregas")


def test_timeouts_padrao_formam_hierarquia():
    assert cliente_dados.HTTP_TIMEOUT == 5.0
    assert cliente_dados.TENTATIVAS == 2
