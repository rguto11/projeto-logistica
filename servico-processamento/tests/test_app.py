"""Testes das rotas do Servico de Processamento (cliente do Dados simulado, sem rede)."""
from datetime import datetime, timedelta

import pytest

import app as modulo_app
from cliente_dados import DadosIndisponivel, ParametroInvalido

client = modulo_app.app.test_client()

PRAZO = datetime(2026, 3, 1, 10, 0, 0)


def _entrega(id_, motorista, atraso):
    return {
        "id": id_, "motorista_id": motorista, "veiculo_id": 1, "regiao": "Centro",
        "status": "ENTREGUE", "distancia_km": 10.0, "custo": 30.0, "peso_kg": 10.0,
        "data_saida": (PRAZO - timedelta(hours=1)).isoformat(), "prazo_previsto": PRAZO.isoformat(),
        "entregue_em": (PRAZO + timedelta(minutes=atraso)).isoformat(),
    }


ENTREGAS = [_entrega(i, 1, 0) for i in range(1, 6)] + [_entrega(6, 1, 150)]
MOTORISTAS = [{"id": 1, "nome": "Ana"}]


@pytest.fixture
def chamadas(monkeypatch):
    """Substitui cliente_dados.listar_todas e registra (recurso, params)."""
    registro = []

    def fake(recurso, params=None):
        registro.append((recurso, params))
        return list(ENTREGAS) if recurso == "entregas" else list(MOTORISTAS)

    monkeypatch.setattr(modulo_app.cliente_dados, "listar_todas", fake)
    return registro


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "servico": "processamento"}


def test_resumo_repassa_filtros_e_ignora_desconhecidos(chamadas):
    resp = client.get("/metricas/resumo?regiao=Centro&data_inicio=2026-03-01&outro=x")
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 6
    assert chamadas == [("entregas", {"regiao": "Centro", "data_inicio": "2026-03-01"})]


@pytest.mark.parametrize("caminho", ["/metricas/status", "/metricas/regioes", "/metricas/outliers-custo"])
def test_rotas_simples_respondem_200(chamadas, caminho):
    assert client.get(caminho).status_code == 200


def test_ranking_padrao(chamadas):
    resp = client.get("/metricas/motoristas/ranking")
    corpo = resp.get_json()
    assert resp.status_code == 200
    assert corpo["min_entregas"] == 5
    assert corpo["top"] is None
    assert corpo["itens"][0]["nome"] == "Ana"


@pytest.mark.parametrize("query", ["top=abc", "top=0", "min_entregas=-1"])
def test_ranking_parametros_invalidos(chamadas, query):
    resp = client.get(f"/metricas/motoristas/ranking?{query}")
    assert resp.status_code == 400
    assert "erro" in resp.get_json()


def test_atrasos_criticos_padrao_e_invalido(chamadas):
    corpo = client.get("/metricas/atrasos-criticos").get_json()
    assert corpo["limite_min"] == 120
    assert corpo["total"] == 1
    assert client.get("/metricas/atrasos-criticos?limite_min=0").status_code == 400


def test_completo_tem_todas_as_secoes(chamadas):
    resp = client.get("/metricas/completo")
    corpo = resp.get_json()
    assert resp.status_code == 200
    assert set(corpo) == {
        "filtros", "resumo", "status", "regioes", "ranking_motoristas",
        "atrasos_criticos", "outliers_custo",
    }
    assert corpo["atrasos_criticos"]["limite_min"] == 120
    # busca unica de entregas + uma de motoristas (para o ranking)
    assert [c[0] for c in chamadas] == ["entregas", "motoristas"]


def test_dados_indisponivel_vira_502(monkeypatch):
    def falha(recurso, params=None):
        raise DadosIndisponivel("x")

    monkeypatch.setattr(modulo_app.cliente_dados, "listar_todas", falha)
    resp = client.get("/metricas/resumo")
    assert resp.status_code == 502
    assert resp.get_json() == {"erro": "servico de dados indisponivel", "detalhe": "x"}


def test_parametro_invalido_do_dados_vira_400(monkeypatch):
    def rejeita(recurso, params=None):
        raise ParametroInvalido("y")

    monkeypatch.setattr(modulo_app.cliente_dados, "listar_todas", rejeita)
    resp = client.get("/metricas/resumo")
    assert resp.status_code == 400
    assert resp.get_json() == {"erro": "y"}


def test_rota_inexistente_e_metodo_nao_permitido():
    assert client.get("/nao-existe").get_json() == {"erro": "recurso nao encontrado"}
    resp = client.post("/health")
    assert resp.status_code == 405
    assert resp.get_json() == {"erro": "metodo nao permitido"}
