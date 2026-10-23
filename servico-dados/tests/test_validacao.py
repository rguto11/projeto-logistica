"""Testes das funcoes de validacao do Servico de Dados (sem banco)."""
from datetime import date, datetime

import pytest

import app as modulo_app

ErroApi = modulo_app.ErroApi


def status_do_erro(funcao, *args, **kwargs):
    with pytest.raises(ErroApi) as info:
        funcao(*args, **kwargs)
    return info.value.status


# ---------------------------------------------------------------- _corpo

def test_corpo_aceita_objeto_json():
    with modulo_app.app.test_request_context("/", method="POST", json={"a": 1}):
        assert modulo_app._corpo() == {"a": 1}


@pytest.mark.parametrize("kwargs", [{"json": [1, 2]}, {"data": "nao e json"}, {}])
def test_corpo_rejeita_lista_texto_e_ausente(kwargs):
    with modulo_app.app.test_request_context("/", method="POST", **kwargs):
        assert status_do_erro(modulo_app._corpo) == 400


# ---------------------------------------------------------------- _texto

def test_texto_valido_e_strip():
    assert modulo_app._texto({"nome": "  Ana  "}, "nome", 10) == "Ana"


def test_texto_obrigatorio_ausente_e_opcional():
    assert status_do_erro(modulo_app._texto, {}, "nome", 10) == 400
    assert modulo_app._texto({}, "nome", 10, obrigatorio=False) is None


@pytest.mark.parametrize("valor", ["", "   ", 123])
def test_texto_vazio_ou_nao_string(valor):
    assert status_do_erro(modulo_app._texto, {"nome": valor}, "nome", 10) == 400


def test_texto_acima_do_maximo():
    assert status_do_erro(modulo_app._texto, {"nome": "x" * 11}, "nome", 10) == 400


# ---------------------------------------------------------------- _opcao

def test_opcao_valida_invalida_e_padrao():
    assert modulo_app._opcao({"s": "A"}, "s", {"A", "B"}) == "A"
    assert status_do_erro(modulo_app._opcao, {"s": "Z"}, "s", {"A", "B"}) == 400
    assert status_do_erro(modulo_app._opcao, {}, "s", {"A", "B"}) == 400
    assert modulo_app._opcao({}, "s", {"A", "B"}, obrigatorio=False, padrao="B") == "B"


# --------------------------------------------------------------- _inteiro

def test_inteiro_limites():
    assert modulo_app._inteiro(5, "n", minimo=1, maximo=10) == 5
    assert status_do_erro(modulo_app._inteiro, 0, "n", minimo=1) == 400
    assert status_do_erro(modulo_app._inteiro, 11, "n", maximo=10) == 400


@pytest.mark.parametrize("valor", [True, 1.5, "1", None])
def test_inteiro_rejeita_bool_float_texto_e_none(valor):
    assert status_do_erro(modulo_app._inteiro, valor, "n") == 400


# ---------------------------------------------------------------- _numero

def test_numero_aceita_int_e_float():
    assert modulo_app._numero(3, "x") == 3
    assert modulo_app._numero(2.5, "x") == 2.5


@pytest.mark.parametrize("valor", [True, "1", None, -0.01])
def test_numero_rejeita_bool_texto_none_e_negativo(valor):
    assert status_do_erro(modulo_app._numero, valor, "x") == 400


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_numero_rejeita_nan_e_infinito(valor):
    assert status_do_erro(modulo_app._numero, valor, "x") == 400


# ------------------------------------------------------------- datas / horas

def test_data_hora_valida():
    assert modulo_app._data_hora("2026-03-01T10:00:00", "t") == datetime(2026, 3, 1, 10, 0)


@pytest.mark.parametrize("texto", ["2026-03-01T10:00:00Z", "2026-03-01T10:00:00-03:00"])
def test_data_hora_com_fuso_mantem_horario_informado_sem_fuso(texto):
    # B6: o deslocamento e descartado; o horario informado e mantido como esta.
    assert modulo_app._data_hora(texto, "t") == datetime(2026, 3, 1, 10, 0)


@pytest.mark.parametrize("valor", ["ontem", 20260301, None])
def test_data_hora_invalida(valor):
    assert status_do_erro(modulo_app._data_hora, valor, "t") == 400


def test_data_valida_e_invalida():
    assert modulo_app._data("2026-03-01", "d") == date(2026, 3, 1)
    assert status_do_erro(modulo_app._data, "01/03/2026", "d") == 400
    assert status_do_erro(modulo_app._data, 5, "d") == 400


# ------------------------------------------------------------ query / paginacao

def test_int_query_ausente_usa_padrao():
    with modulo_app.app.test_request_context("/"):
        assert modulo_app._int_query("limit", 100, 1) == 100


@pytest.mark.parametrize("query", ["limit=abc", "limit=0", "limit=1001"])
def test_int_query_invalido(query):
    with modulo_app.app.test_request_context(f"/?{query}"):
        assert status_do_erro(modulo_app._int_query, "limit", 100, 1, 1000) == 400


def test_paginacao_padrao():
    with modulo_app.app.test_request_context("/"):
        assert modulo_app._paginacao() == (100, 0)


# ---------------------------------------------------------- consistencia / placa

def test_checar_consistencia_quatro_combinacoes():
    modulo_app._checar_consistencia("ENTREGUE", datetime(2026, 3, 1))
    modulo_app._checar_consistencia("EM_ROTA", None)
    assert status_do_erro(modulo_app._checar_consistencia, "ENTREGUE", None) == 400
    assert status_do_erro(modulo_app._checar_consistencia, "EM_ROTA", datetime(2026, 3, 1)) == 400


@pytest.mark.parametrize("placa,valida", [
    ("ABC1D23", True), ("ABC1234", True), ("abc1d23", False), ("AB1C234", False),
])
def test_placa_regex(placa, valida):
    assert bool(modulo_app.PLACA_RE.match(placa)) is valida
