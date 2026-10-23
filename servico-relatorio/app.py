"""Servico de Relatorio: orquestra Dados + Processamento e entrega JSON, CSV ou HTML."""
import os
from datetime import datetime, timedelta, timezone

import requests
from flask import Flask, Response, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

import formatadores

DADOS_URL = os.environ.get("DADOS_URL", "http://servico-dados:8001").rstrip("/")
PROCESSAMENTO_URL = os.environ.get("PROCESSAMENTO_URL", "http://servico-processamento:8002").rstrip("/")
# Maior que o pior caso do Processamento (~16 s) e menor que o --timeout 60 do gunicorn.
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "30"))
FORMATOS = ["json", "csv", "html"]
FILTROS = ("regiao", "data_inicio", "data_fim")
FUSO = timezone(timedelta(hours=-3))  # horario de Brasilia

app = Flask(__name__)
app.json.ensure_ascii = False


@app.template_filter("br")
def _formato_br(valor, casas=2):
    """Numero no padrao brasileiro: 1.234,56."""
    if valor is None:
        return "-"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


class FalhaDependencia(Exception):
    def __init__(self, servico, detalhe, status=502):
        super().__init__(detalhe)
        self.servico, self.detalhe, self.status = servico, detalhe, status


@app.errorhandler(FalhaDependencia)
def _falha_dependencia(e):
    if e.status == 400:
        return jsonify({"erro": "filtros invalidos", "detalhe": e.detalhe}), 400
    return jsonify({"erro": "falha ao consultar servico dependente",
                    "servico": e.servico, "detalhe": e.detalhe}), 502


@app.errorhandler(HTTPException)
def _erro_http(e):
    mensagens = {404: "recurso nao encontrado", 405: "metodo nao permitido"}
    return jsonify({"erro": mensagens.get(e.code, e.description)}), e.code


def _consultar(servico, url, params=None):
    try:
        resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    except requests.RequestException as exc:
        raise FalhaDependencia(servico, str(exc)) from exc
    if resp.status_code == 400:
        try:
            detalhe = resp.json().get("erro", "parametros invalidos")
        except ValueError:
            detalhe = "parametros invalidos"
        raise FalhaDependencia(servico, detalhe, status=400)
    if not resp.ok:
        raise FalhaDependencia(servico, f"HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise FalhaDependencia(servico, "resposta nao e JSON valido") from exc


def _observacoes(ind):
    obs = []
    resumo = ind["resumo"]
    obs.append(
        f'{resumo["pct_no_prazo"]:.2f}% das {resumo["finalizadas"]} entregas concluídas '
        f'chegaram no prazo; atraso médio das atrasadas: {resumo["atraso_medio_min"]:.2f} min.'
    )
    regioes = ind["regioes"]
    if regioes:
        melhor, pior = regioes[0], regioes[-1]
        obs.append(f'Melhor região em pontualidade: {melhor["regiao"]} ({melhor["pct_no_prazo"]:.2f}% no prazo).')
        obs.append(f'Pior região em pontualidade: {pior["regiao"]} ({pior["pct_no_prazo"]:.2f}% no prazo).')
    ranking = ind["ranking_motoristas"]
    if ranking:
        melhor_motorista = ranking[0]
        obs.append(
            f'Motorista com melhor desempenho: {melhor_motorista["nome"]} '
            f'({melhor_motorista["pct_no_prazo"]:.2f}% no prazo).'
        )
    criticos = ind["atrasos_criticos"]
    obs.append(f'{criticos["total"]} entregas com atraso crítico (>= {criticos["limite_min"]} min).')
    obs.append(f'{ind["outliers_custo"]["total"]} entregas com custo por km atípico (regra do IQR).')
    return obs


def montar_relatorio():
    filtros = {c: request.args[c] for c in FILTROS if request.args.get(c)}
    url_resumo = f"{DADOS_URL}/resumo"
    url_completo = f"{PROCESSAMENTO_URL}/metricas/completo"
    base = _consultar("dados", url_resumo)
    completo = _consultar("processamento", url_completo, filtros)
    completo.pop("filtros", None)
    return {
        "titulo": "Relatório de Desempenho de Entregas",
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "filtros": filtros,
        "fontes": {"dados": url_resumo, "processamento": url_completo},
        "base": base,
        "indicadores": completo,
        "observacoes": _observacoes(completo),
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok", "servico": "relatorio"})


@app.get("/")
def indice():
    return jsonify({
        "servico": "relatorio",
        "descricao": "Relatório consolidado de entregas (orquestra Dados e Processamento)",
        "formatos": FORMATOS,
        "exemplos": [f"/relatorio?formato={f}" for f in FORMATOS],
        "filtros_opcionais": list(FILTROS),
    })


@app.get("/relatorio")
def relatorio():
    formato = request.args.get("formato", "json").lower()
    if formato not in FORMATOS:
        return jsonify({"erro": "formato invalido", "validos": FORMATOS}), 400
    dados = montar_relatorio()
    if formato == "csv":
        return Response(
            formatadores.to_csv(dados),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=relatorio_entregas.csv"},
        )
    if formato == "html":
        return render_template("relatorio.html", r=dados)
    return jsonify(dados)
