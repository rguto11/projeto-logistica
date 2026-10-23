"""Formatadores do relatorio consolidado."""
import csv
import io

CABECALHO = ["secao", "item", "metrica", "valor"]


def _linhas(relatorio):
    base = relatorio["base"]
    ind = relatorio["indicadores"]
    for chave in ("motoristas", "veiculos", "entregas"):
        yield "base", "cadastro", chave, base[chave]

    for metrica, valor in ind["resumo"].items():
        if metrica != "por_status":
            yield "resumo", "geral", metrica, valor

    for status, qtd in ind["status"].items():
        yield "status", status, "entregas", qtd

    for r in ind["regioes"]:
        for metrica, valor in r.items():
            if metrica != "regiao":
                yield "regioes", r["regiao"], metrica, valor

    for m in ind["ranking_motoristas"]:
        item = f'{m["posicao"]} - {m["nome"]}'
        for metrica, valor in m.items():
            if metrica not in ("posicao", "nome"):
                yield "ranking", item, metrica, valor

    criticos = ind["atrasos_criticos"]
    yield "atrasos_criticos", "geral", "total", criticos["total"]
    for a in criticos["itens"]:
        for metrica, valor in a.items():
            if metrica != "id":
                yield "atrasos_criticos", f'entrega {a["id"]}', metrica, valor

    out = ind["outliers_custo"]
    for metrica in ("q1", "q3", "iqr", "limite_superior", "analisadas", "total"):
        yield "outliers_custo", "geral", metrica, out[metrica]
    for o in out["itens"]:
        yield "outliers_custo", f'entrega {o["id"]}', "custo_km", o["custo_km"]


def to_csv(relatorio):
    buf = io.StringIO()
    escritor = csv.writer(buf, lineterminator="\n")
    escritor.writerow(CABECALHO)
    for linha in _linhas(relatorio):
        escritor.writerow(linha)
    return buf.getvalue()
