import csv
import io

import formatadores


def _relatorio(base, completo):
    return {"base": base, "indicadores": completo}


def _linhas(texto):
    return list(csv.reader(io.StringIO(texto)))


def test_cabecalho_e_linhas_principais(base, completo):
    linhas = _linhas(formatadores.to_csv(_relatorio(base, completo)))
    assert linhas[0] == ["secao", "item", "metrica", "valor"]
    assert ["base", "cadastro", "motoristas", "20"] in linhas
    assert ["status", "ENTREGUE", "entregas", "339"] in linhas
    assert ["regioes", "Centro", "pct_no_prazo", "86.96"] in linhas
    assert ["ranking", "1 - Paulo Roberto Mendes", "pct_no_prazo", "95.24"] in linhas
    assert ["atrasos_criticos", "entrega 350", "atraso_min", "298"] in linhas


def test_por_status_nao_aparece_em_resumo_nem_id_em_atrasos(base, completo):
    linhas = _linhas(formatadores.to_csv(_relatorio(base, completo)))
    assert not [linha for linha in linhas if linha[0] == "resumo" and linha[2] == "por_status"]
    assert not [linha for linha in linhas if linha[0] == "atrasos_criticos" and linha[2] == "id"]


def test_secao_outliers(base, completo):
    linhas = _linhas(formatadores.to_csv(_relatorio(base, completo)))
    outliers = {(linha[1], linha[2]): linha[3] for linha in linhas if linha[0] == "outliers_custo"}
    for metrica, esperado in (("q1", "2.27"), ("q3", "4.01"), ("iqr", "1.75"),
                              ("limite_superior", "6.63"), ("analisadas", "339"), ("total", "1")):
        assert outliers[("geral", metrica)] == esperado
    assert outliers[("entrega 324", "custo_km")] == "9.52"


def test_toda_linha_tem_quatro_colunas(base, completo):
    assert all(len(linha) == 4 for linha in _linhas(formatadores.to_csv(_relatorio(base, completo))))


def test_nome_com_virgula_e_escapado(base, completo):
    completo["ranking_motoristas"][0]["nome"] = "Silva, João"
    texto = formatadores.to_csv(_relatorio(base, completo))
    assert '"1 - Silva, João"' in texto
    assert ["ranking", "1 - Silva, João", "pct_no_prazo", "95.24"] in _linhas(texto)


def test_listas_vazias_nao_quebram(base, completo):
    completo["ranking_motoristas"] = []
    completo["regioes"] = []
    completo["atrasos_criticos"] = {"limite_min": 120, "total": 0, "itens": []}
    completo["outliers_custo"] = {
        "q1": None, "q3": None, "iqr": None, "limite_superior": None,
        "analisadas": 0, "total": 0, "ids": [], "itens": [],
    }
    linhas = _linhas(formatadores.to_csv(_relatorio(base, completo)))
    assert not [linha for linha in linhas if linha[0] in ("ranking", "regioes")]
    assert ["atrasos_criticos", "geral", "total", "0"] in linhas
