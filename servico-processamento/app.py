"""Servico de Processamento: busca dados via HTTP no Servico de Dados e calcula metricas."""
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

import calculos
import cliente_dados
from cliente_dados import DadosIndisponivel, ParametroInvalido

FILTROS = ("regiao", "data_inicio", "data_fim")
RANKING_TOP_COMPLETO = 10
ATRASOS_CRITICOS_MAX_COMPLETO = 10

app = Flask(__name__)
app.json.ensure_ascii = False


@app.errorhandler(DadosIndisponivel)
def _dados_indisponivel(e):
    return jsonify({"erro": "servico de dados indisponivel", "detalhe": str(e)}), 502


@app.errorhandler(ParametroInvalido)
def _parametro_invalido(e):
    return jsonify({"erro": str(e)}), 400


@app.errorhandler(HTTPException)
def _erro_http(e):
    mensagens = {404: "recurso nao encontrado", 405: "metodo nao permitido"}
    return jsonify({"erro": mensagens.get(e.code, e.description)}), e.code


def _filtros():
    return {c: request.args[c] for c in FILTROS if request.args.get(c)}


def _entregas():
    return cliente_dados.listar_todas("entregas", _filtros())


def _int_arg(nome, padrao, minimo):
    bruto = request.args.get(nome)
    if bruto is None:
        return padrao
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ParametroInvalido(f"parametro '{nome}' deve ser inteiro") from exc
    if valor < minimo:
        raise ParametroInvalido(f"parametro '{nome}' deve ser >= {minimo}")
    return valor


def _ranking(entregas, top, min_entregas):
    motoristas = cliente_dados.listar_todas("motoristas")
    return calculos.ranking_motoristas(entregas, motoristas, top=top, min_entregas=min_entregas)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "servico": "processamento"})


@app.get("/metricas/resumo")
def metricas_resumo():
    return jsonify(calculos.resumo(_entregas()))


@app.get("/metricas/status")
def metricas_status():
    return jsonify(calculos.resumo(_entregas())["por_status"])


@app.get("/metricas/regioes")
def metricas_regioes():
    return jsonify(calculos.por_regiao(_entregas()))


@app.get("/metricas/motoristas/ranking")
def metricas_ranking():
    top = _int_arg("top", None, 1)
    min_entregas = _int_arg("min_entregas", calculos.MIN_ENTREGAS_RANKING, 0)
    return jsonify({"top": top, "min_entregas": min_entregas,
                    "itens": _ranking(_entregas(), top, min_entregas)})


@app.get("/metricas/atrasos-criticos")
def metricas_atrasos_criticos():
    limite = _int_arg("limite_min", calculos.LIMITE_CRITICO_MIN, 1)
    itens = calculos.atrasos_criticos(_entregas(), limite)
    return jsonify({"limite_min": limite, "total": len(itens), "itens": itens})


@app.get("/metricas/outliers-custo")
def metricas_outliers():
    return jsonify(calculos.outliers_custo_km(_entregas()))


@app.get("/metricas/completo")
def metricas_completo():
    entregas = _entregas()  # busca unica, reaproveitada em todos os calculos
    resumo = calculos.resumo(entregas)
    criticos = calculos.atrasos_criticos(entregas, calculos.LIMITE_CRITICO_MIN)
    return jsonify({
        "filtros": _filtros(),
        "resumo": resumo,
        "status": resumo["por_status"],
        "regioes": calculos.por_regiao(entregas),
        "ranking_motoristas": _ranking(entregas, RANKING_TOP_COMPLETO, calculos.MIN_ENTREGAS_RANKING),
        "atrasos_criticos": {
            "limite_min": calculos.LIMITE_CRITICO_MIN,
            "total": len(criticos),
            "itens": criticos[:ATRASOS_CRITICOS_MAX_COMPLETO],
        },
        "outliers_custo": calculos.outliers_custo_km(entregas),
    })
