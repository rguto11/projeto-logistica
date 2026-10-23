"""Testes das rotas do Servico de Relatorio (requests.get simulado, sem rede)."""
import pytest
import requests
from conftest import FakeResp

import app as modulo_app

client = modulo_app.app.test_client()


@pytest.fixture
def chamadas(monkeypatch, base, completo):
    """Simula Dados e Processamento: roteia pelo sufixo da URL e registra (url, params, timeout)."""
    registro = []

    def fake(url, params=None, timeout=None):
        registro.append((url, params, timeout))
        return FakeResp(200, base if url.endswith("/resumo") else completo)

    monkeypatch.setattr(modulo_app.requests, "get", fake)
    return registro


def _instalar(monkeypatch, resposta_dados, resposta_proc):
    """Dados e Processamento com respostas independentes (objeto FakeResp ou excecao)."""
    def fake(url, params=None, timeout=None):
        item = resposta_dados if url.endswith("/resumo") else resposta_proc
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(modulo_app.requests, "get", fake)


def test_health():
    assert client.get("/health").get_json() == {"status": "ok", "servico": "relatorio"}


def test_indice_lista_formatos_e_filtros():
    corpo = client.get("/").get_json()
    assert corpo["formatos"] == ["json", "csv", "html"]
    assert corpo["filtros_opcionais"] == ["regiao", "data_inicio", "data_fim"]


def test_relatorio_json_padrao(chamadas):
    resp = client.get("/relatorio")
    corpo = resp.get_json()
    assert resp.status_code == 200
    assert set(corpo) == {"titulo", "gerado_em", "filtros", "fontes", "base", "indicadores", "observacoes"}
    assert "filtros" not in corpo["indicadores"]
    assert corpo["base"]["entregas"] == 400


def test_relatorio_csv(chamadas):
    resp = client.get("/relatorio?formato=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "relatorio_entregas.csv" in resp.headers["Content-Disposition"]
    assert resp.get_data(as_text=True).startswith("secao,item,metrica,valor")


def test_relatorio_html(chamadas):
    resp = client.get("/relatorio?formato=html")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert "Relatório de Desempenho de Entregas" in resp.get_data(as_text=True)


def test_formato_invalido(chamadas):
    resp = client.get("/relatorio?formato=xml")
    assert resp.status_code == 400
    assert resp.get_json() == {"erro": "formato invalido", "validos": ["json", "csv", "html"]}


def test_filtros_e_timeout_chegam_ao_processamento(chamadas):
    client.get("/relatorio?regiao=Centro&outro=x")
    url, params, timeout = chamadas[-1]
    assert url.endswith("/metricas/completo")
    assert params == {"regiao": "Centro"}
    assert timeout == modulo_app.HTTP_TIMEOUT


def test_falha_de_rede_no_dados_nomeia_dados(monkeypatch, completo):
    _instalar(monkeypatch, requests.ConnectionError("recusada"), FakeResp(200, completo))
    resp = client.get("/relatorio")
    assert resp.status_code == 502
    assert resp.get_json()["servico"] == "dados"


def test_falha_de_rede_no_processamento_nomeia_processamento(monkeypatch, base):
    _instalar(monkeypatch, FakeResp(200, base), requests.ConnectionError("recusada"))
    resp = client.get("/relatorio")
    assert resp.status_code == 502
    assert resp.get_json()["servico"] == "processamento"


def test_processamento_502_nomeia_processamento(monkeypatch, base):
    _instalar(monkeypatch, FakeResp(200, base), FakeResp(502, {"erro": "servico de dados indisponivel"}))
    corpo = client.get("/relatorio").get_json()
    assert corpo["servico"] == "processamento"
    assert corpo["detalhe"] == "HTTP 502"


def test_processamento_400_vira_filtros_invalidos(monkeypatch, base):
    _instalar(monkeypatch, FakeResp(200, base), FakeResp(400, {"erro": "data invalida"}))
    resp = client.get("/relatorio?data_inicio=x")
    assert resp.status_code == 400
    assert resp.get_json() == {"erro": "filtros invalidos", "detalhe": "data invalida"}


def test_processamento_400_com_json_invalido(monkeypatch, base):
    _instalar(monkeypatch, FakeResp(200, base), FakeResp(400, json_invalido=True))
    assert client.get("/relatorio").get_json()["detalhe"] == "parametros invalidos"


def test_processamento_200_com_json_invalido_vira_502(monkeypatch, base):
    _instalar(monkeypatch, FakeResp(200, base), FakeResp(200, json_invalido=True))
    resp = client.get("/relatorio")
    assert resp.status_code == 502
    assert resp.get_json()["detalhe"] == "resposta nao e JSON valido"


def test_observacoes_citam_melhor_e_pior_regiao(completo):
    obs = modulo_app._observacoes(completo)
    assert len(obs) >= 5
    assert any("Melhor região" in o and "Centro" in o for o in obs)
    assert any("Pior região" in o and "Zona Norte" in o for o in obs)


def test_filtro_br():
    formato_br = modulo_app.app.jinja_env.filters["br"]
    assert formato_br(1234.5) == "1.234,50"
    assert formato_br(None) == "-"


def test_timeout_padrao_cobre_pior_caso_do_processamento():
    assert modulo_app.HTTP_TIMEOUT == 30.0
    assert modulo_app.HTTP_TIMEOUT > 16
