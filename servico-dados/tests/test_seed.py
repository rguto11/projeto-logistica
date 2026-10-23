"""Testes do gerador deterministico de dados sinteticos."""
import re
from collections import Counter

import pytest

import seed

PLACA_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


@pytest.fixture(scope="module")
def dados():
    return seed.gerar_dados()


def test_contagens(dados):
    assert len(dados["motoristas"]) == 20
    assert len(dados["veiculos"]) == 12
    assert len(dados["entregas"]) == 400


def test_veiculos_por_tipo(dados):
    assert Counter(v[1] for v in dados["veiculos"]) == {"MOTO": 3, "VAN": 4, "CAMINHAO_LEVE": 3, "CAMINHAO": 2}


def test_determinismo():
    assert seed.gerar_dados() == seed.gerar_dados()


def test_placas_unicas_e_validas(dados):
    placas = [v[0] for v in dados["veiculos"]]
    assert len(set(placas)) == len(placas)
    assert all(PLACA_RE.match(p) for p in placas)


def test_entregas_referenciam_indices_validos(dados):
    assert all(e[0] in range(20) and e[1] in range(12) for e in dados["entregas"])


def test_regiao_e_status_validos(dados):
    assert {e[2] for e in dados["entregas"]} <= set(seed.REGIOES)
    assert {e[3] for e in dados["entregas"]} <= {"ENTREGUE", "EM_ROTA", "CANCELADA", "FALHA"}


def test_entregue_em_somente_quando_entregue(dados):
    assert all((e[9] is not None) == (e[3] == "ENTREGUE") for e in dados["entregas"])


def test_valores_satisfazem_restricoes_do_schema(dados):
    # peso_kg > 0, distancia_km >= 0 e custo >= 0 (CHECKs de schema.sql)
    assert all(e[6] > 0 and e[4] >= 0 and e[5] >= 0 for e in dados["entregas"])


def test_entregas_ordenadas_por_data_saida(dados):
    saidas = [e[7] for e in dados["entregas"]]
    assert saidas == sorted(saidas)
