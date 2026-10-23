"""Testes das rotas do Servico de Dados com o acesso ao banco simulado (sem PostgreSQL)."""
import json

import psycopg2
import pytest
from psycopg2 import errors

import app as modulo_app

client = modulo_app.app.test_client()

ENTREGA_VALIDA = {
    "motorista_id": 1, "veiculo_id": 1, "regiao": "Centro", "status": "EM_ROTA",
    "distancia_km": 10.5, "custo": 30.0, "peso_kg": 12.0,
    "data_saida": "2026-03-01T09:00:00", "prazo_previsto": "2026-03-01T10:00:00",
}


@pytest.fixture
def banco_proibido(monkeypatch):
    """Qualquer acesso ao banco falha o teste: a validacao deve barrar antes."""
    def proibido(*args, **kwargs):
        raise AssertionError("a requisicao nao deveria chegar ao banco")

    monkeypatch.setattr(modulo_app.db, "consultar_um", proibido)
    monkeypatch.setattr(modulo_app.db, "consultar", proibido)
    monkeypatch.setattr(modulo_app.db, "executar_retornando", proibido)


def _levantar(excecao):
    def funcao(*args, **kwargs):
        raise excecao

    return funcao


# --------------------------------------------------------------- POST /veiculos

@pytest.mark.parametrize("corpo", [
    {"placa": "xx", "tipo": "VAN", "capacidade_kg": 1000, "ano": 2024},
    {"placa": "XYZ1A23", "tipo": "BICICLETA", "capacidade_kg": 1000, "ano": 2024},
])
def test_criar_veiculo_invalido(banco_proibido, corpo):
    assert client.post("/veiculos", json=corpo).status_code == 400


def test_criar_veiculo_corpo_nao_json(banco_proibido):
    assert client.post("/veiculos", data="texto", content_type="text/plain").status_code == 400


def test_criar_veiculo_placa_duplicada_vira_409(monkeypatch):
    monkeypatch.setattr(modulo_app.db, "executar_retornando", _levantar(errors.UniqueViolation()))
    resp = client.post("/veiculos", json={"placa": "XYZ1A23", "tipo": "VAN", "capacidade_kg": 1200, "ano": 2024})
    assert resp.status_code == 409
    assert "XYZ1A23" in resp.get_json()["erro"]


# -------------------------------------------------------------- POST /entregas

def test_criar_entrega_peso_zero_vira_400(banco_proibido):
    resp = client.post("/entregas", json={**ENTREGA_VALIDA, "peso_kg": 0})
    assert resp.status_code == 400
    assert resp.get_json() == {"erro": "campo 'peso_kg' deve ser > 0"}


def test_criar_entrega_nan_vira_400(banco_proibido):
    # json.dumps serializa float('nan') como NaN, que o parser do Flask aceita.
    corpo = json.dumps({**ENTREGA_VALIDA, "peso_kg": float("nan")})
    resp = client.post("/entregas", data=corpo, content_type="application/json")
    assert resp.status_code == 400
    assert "finito" in resp.get_json()["erro"]


def test_criar_entrega_distancia_negativa_vira_400(banco_proibido):
    assert client.post("/entregas", json={**ENTREGA_VALIDA, "distancia_km": -1}).status_code == 400


# ------------------------------------------------------------------ erros gerais

def test_rota_inexistente_e_metodo_nao_permitido():
    assert client.get("/nao-existe").get_json() == {"erro": "recurso nao encontrado"}
    assert client.put("/veiculos").status_code == 405


@pytest.mark.parametrize("excecao", [psycopg2.OperationalError("caiu"), psycopg2.InterfaceError("conexao fechada")])
def test_erro_de_conexao_com_banco_vira_503(monkeypatch, excecao):
    monkeypatch.setattr(modulo_app.db, "consultar_um", _levantar(excecao))
    resp = client.get("/resumo")
    assert resp.status_code == 503
    assert resp.get_json() == {"erro": "banco de dados indisponivel"}


def test_health_com_banco_fora_retorna_503(monkeypatch):
    monkeypatch.setattr(modulo_app.db, "consultar_um", _levantar(psycopg2.OperationalError("caiu")))
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.get_json()["status"] == "indisponivel"


def test_excecao_generica_vira_500_sem_stack_trace(monkeypatch):
    monkeypatch.setattr(modulo_app.db, "consultar_um", _levantar(RuntimeError("segredo interno")))
    resp = client.get("/resumo")
    assert resp.status_code == 500
    assert resp.get_json() == {"erro": "erro interno do servidor"}
    assert "segredo interno" not in resp.get_data(as_text=True)
