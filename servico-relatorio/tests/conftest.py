"""Fixtures compartilhadas dos testes do Servico de Relatorio (sem rede)."""
import pytest


class FakeResp:
    """Resposta HTTP minima com a interface usada por app._consultar."""

    def __init__(self, status_code, payload=None, json_invalido=False):
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload
        self._json_invalido = json_invalido

    def json(self):
        if self._json_invalido:
            raise ValueError("json invalido")
        return self._payload


@pytest.fixture
def base():
    return {"motoristas": 20, "veiculos": 12, "entregas": 400}


@pytest.fixture
def completo():
    """Versao reduzida do payload de /metricas/completo do Servico de Processamento."""
    return {
        "filtros": {},
        "resumo": {
            "total": 400,
            "por_status": {"ENTREGUE": 339, "EM_ROTA": 30, "CANCELADA": 10, "FALHA": 21},
            "finalizadas": 339,
            "no_prazo": 254,
            "atrasadas": 85,
            "pct_no_prazo": 74.93,
            "atraso_medio_min": 62.82,
            "atraso_medio_geral_min": 15.75,
            "atraso_maximo_min": 298,
            "distancia_total_km": 8310.35,
            "custo_total": 30629.76,
            "custo_por_km": 3.69,
        },
        "status": {"ENTREGUE": 339, "EM_ROTA": 30, "CANCELADA": 10, "FALHA": 21},
        "regioes": [
            {"regiao": "Centro", "total": 81, "entregues": 69, "pct_no_prazo": 86.96,
             "atraso_medio_min": 76.78, "custo_por_km": 3.2},
            {"regiao": "Zona Norte", "total": 79, "entregues": 68, "pct_no_prazo": 67.65,
             "atraso_medio_min": 66.91, "custo_por_km": 3.62},
        ],
        "ranking_motoristas": [
            {"posicao": 1, "motorista_id": 8, "nome": "Paulo Roberto Mendes", "entregas_finalizadas": 21,
             "pct_no_prazo": 95.24, "atraso_medio_min": 31.0, "custo_por_km": 4.04,
             "distancia_total_km": 499.03},
            {"posicao": 2, "motorista_id": 4, "nome": "Rafael Henrique Costa", "entregas_finalizadas": 13,
             "pct_no_prazo": 92.31, "atraso_medio_min": 59.0, "custo_por_km": 3.43,
             "distancia_total_km": 268.0},
        ],
        "atrasos_criticos": {
            "limite_min": 120,
            "total": 7,
            "itens": [
                {"id": 350, "motorista_id": 9, "regiao": "Zona Sul", "atraso_min": 298,
                 "prazo_previsto": "2026-05-19T18:56:00", "entregue_em": "2026-05-19T23:54:00"},
            ],
        },
        "outliers_custo": {
            "q1": 2.27, "q3": 4.01, "iqr": 1.75, "limite_superior": 6.63,
            "analisadas": 339, "total": 1, "ids": [324],
            "itens": [{"id": 324, "custo_km": 9.52}],
        },
    }
