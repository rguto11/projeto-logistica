from datetime import datetime, timedelta

import calculos

PRAZO = "2026-03-01T10:00:00"


def entrega(id_, motorista=1, regiao="Centro", status="ENTREGUE", atraso=0,
            km=10.0, custo=30.0):
    """Monta uma entrega; 'atraso' em minutos (negativo = adiantada)."""
    prazo = datetime.fromisoformat(PRAZO)
    entregue = (prazo + timedelta(minutes=atraso)).isoformat() if status == "ENTREGUE" else None
    return {
        "id": id_, "motorista_id": motorista, "veiculo_id": 1, "regiao": regiao,
        "status": status, "distancia_km": km, "custo": custo, "peso_kg": 10.0,
        "data_saida": "2026-03-01T09:00:00", "prazo_previsto": PRAZO, "entregue_em": entregue,
    }


def test_atraso_no_prazo_atrasada_e_cancelada():
    assert calculos.atraso_min(entrega(1, atraso=-10)) == 0
    assert calculos.atraso_min(entrega(2, atraso=0)) == 0
    assert calculos.atraso_min(entrega(3, atraso=45)) == 45
    assert calculos.atraso_min(entrega(4, status="CANCELADA")) is None


def test_resumo_mistura_de_status():
    dados = [
        entrega(1, atraso=-5, km=10, custo=20),
        entrega(2, atraso=30, km=10, custo=40),
        entrega(3, atraso=60, km=20, custo=60),
        entrega(4, status="CANCELADA"),
        entrega(5, status="EM_ROTA"),
        entrega(6, status="FALHA"),
    ]
    r = calculos.resumo(dados)
    assert r["total"] == 6
    assert r["por_status"] == {"ENTREGUE": 3, "EM_ROTA": 1, "CANCELADA": 1, "FALHA": 1}
    assert r["finalizadas"] == 3
    assert r["no_prazo"] == 1
    assert r["atrasadas"] == 2
    assert r["pct_no_prazo"] == 33.33
    assert r["atraso_medio_min"] == 45.0          # media so das atrasadas
    assert r["atraso_medio_geral_min"] == 30.0    # media de todas as ENTREGUE
    assert r["atraso_maximo_min"] == 60
    assert r["distancia_total_km"] == 40.0
    assert r["custo_total"] == 120.0
    assert r["custo_por_km"] == 3.0


def test_resumo_sem_entregas_concluidas_nao_divide_por_zero():
    r = calculos.resumo([entrega(1, status="CANCELADA"), entrega(2, status="EM_ROTA")])
    assert r["finalizadas"] == 0
    assert r["pct_no_prazo"] == 0.0
    assert r["atraso_medio_min"] == 0.0
    assert r["atraso_maximo_min"] == 0
    assert r["custo_por_km"] == 0.0
    assert calculos.resumo([])["total"] == 0


def test_por_regiao_ordenado_por_pct_no_prazo():
    dados = [
        entrega(1, regiao="Centro", atraso=0),
        entrega(2, regiao="Centro", atraso=0),
        entrega(3, regiao="Zona Leste", atraso=0),
        entrega(4, regiao="Zona Leste", atraso=50),
    ]
    regioes = calculos.por_regiao(dados)
    assert [r["regiao"] for r in regioes] == ["Centro", "Zona Leste"]
    assert regioes[0]["pct_no_prazo"] == 100.0
    assert regioes[1]["pct_no_prazo"] == 50.0
    assert regioes[1]["atraso_medio_min"] == 50.0


def test_ranking_desempate_e_min_entregas():
    motoristas = [
        {"id": 1, "nome": "Bruno"}, {"id": 2, "nome": "Ana"},
        {"id": 3, "nome": "Carla"}, {"id": 4, "nome": "Davi"},
    ]
    dados = []
    n = 0
    # Bruno e Ana: 4/5 no prazo; Ana com atraso medio menor (10 x 20)
    for mid, atraso_ruim in ((1, 20), (2, 10)):
        for i in range(5):
            n += 1
            dados.append(entrega(n, motorista=mid, atraso=atraso_ruim if i == 0 else 0))
    # Carla: 5/5 no prazo (lider)
    for _ in range(5):
        n += 1
        dados.append(entrega(n, motorista=3, atraso=0))
    # Davi: so 2 entregas -> excluido
    for _ in range(2):
        n += 1
        dados.append(entrega(n, motorista=4, atraso=0))

    ranking = calculos.ranking_motoristas(dados, motoristas, min_entregas=5)
    assert [r["nome"] for r in ranking] == ["Carla", "Ana", "Bruno"]
    assert [r["posicao"] for r in ranking] == [1, 2, 3]
    assert ranking[0]["pct_no_prazo"] == 100.0
    assert ranking[1]["pct_no_prazo"] == ranking[2]["pct_no_prazo"] == 80.0
    assert len(calculos.ranking_motoristas(dados, motoristas, top=2)) == 2
    assert "Davi" in [r["nome"] for r in calculos.ranking_motoristas(dados, motoristas, min_entregas=2)]


def test_atrasos_criticos_limite_119_vs_120():
    dados = [entrega(1, atraso=119), entrega(2, atraso=120), entrega(3, atraso=200),
             entrega(4, status="FALHA")]
    criticos = calculos.atrasos_criticos(dados)
    assert [c["id"] for c in criticos] == [3, 2]
    assert criticos[0]["atraso_min"] == 200
    assert calculos.atrasos_criticos(dados, limite_min=119)[-1]["id"] == 1


def test_outliers_custo_km_iqr():
    dados = [entrega(i, km=10, custo=30 + i) for i in range(1, 9)]  # 3,1..3,8 R$/km
    dados.append(entrega(99, km=10, custo=300))                     # 30 R$/km
    r = calculos.outliers_custo_km(dados)
    assert r["ids"] == [99]
    assert r["itens"][0]["custo_km"] == 30.0
    assert r["limite_superior"] < 30.0


def test_outliers_custo_km_poucos_pontos():
    r = calculos.outliers_custo_km([entrega(1), entrega(2), entrega(3)])
    assert r["ids"] == []
    assert r["limite_superior"] is None


def test_outliers_ignora_distancia_zero():
    dados = [entrega(i, km=10, custo=30) for i in range(1, 6)] + [entrega(9, km=0, custo=5)]
    r = calculos.outliers_custo_km(dados)
    assert r["analisadas"] == 5
    assert r["ids"] == []
