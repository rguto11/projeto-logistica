"""Servico de Dados: API REST sobre PostgreSQL (motoristas, veiculos, entregas)."""
import math
import re
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from flask import Flask, jsonify, request
from flask.json.provider import DefaultJSONProvider
from psycopg2 import errors
from werkzeug.exceptions import HTTPException

import db

REGIOES = {"Centro", "Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste"}
STATUS = {"ENTREGUE", "EM_ROTA", "CANCELADA", "FALHA"}
TIPOS_VEICULO = {"MOTO", "VAN", "CAMINHAO_LEVE", "CAMINHAO"}
CATEGORIAS_CNH = {"A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"}
PLACA_RE = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")
LIMIT_PADRAO = 100
LIMIT_MAXIMO = 1000


class ProvedorJSON(DefaultJSONProvider):
    """Numeric vira numero JSON (e nao texto); datas viram ISO-8601."""
    ensure_ascii = False

    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = ProvedorJSON(app)


class ErroApi(Exception):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


@app.errorhandler(ErroApi)
def _erro_api(e):
    return jsonify({"erro": e.mensagem}), e.status


@app.errorhandler(HTTPException)
def _erro_http(e):
    mensagens = {404: "recurso nao encontrado", 405: "metodo nao permitido"}
    return jsonify({"erro": mensagens.get(e.code, e.description)}), e.code


@app.errorhandler(psycopg2.OperationalError)
@app.errorhandler(psycopg2.InterfaceError)
def _erro_banco_indisponivel(e):
    return jsonify({"erro": "banco de dados indisponivel"}), 503


@app.errorhandler(Exception)
def _erro_interno(e):
    app.logger.exception("erro interno")
    return jsonify({"erro": "erro interno do servidor"}), 500


# ----------------------------------------------------------------- validacao

def _corpo():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ErroApi(400, "corpo da requisicao deve ser um objeto JSON")
    return dados


def _texto(dados, campo, maximo, obrigatorio=True):
    valor = dados.get(campo)
    if valor is None:
        if obrigatorio:
            raise ErroApi(400, f"campo '{campo}' e obrigatorio")
        return None
    if not isinstance(valor, str) or not valor.strip():
        raise ErroApi(400, f"campo '{campo}' deve ser texto nao vazio")
    valor = valor.strip()
    if len(valor) > maximo:
        raise ErroApi(400, f"campo '{campo}' excede {maximo} caracteres")
    return valor


def _opcao(dados, campo, validos, obrigatorio=True, padrao=None):
    valor = dados.get(campo)
    if valor is None:
        if obrigatorio:
            raise ErroApi(400, f"campo '{campo}' e obrigatorio")
        return padrao
    if not isinstance(valor, str) or valor not in validos:
        raise ErroApi(400, f"campo '{campo}' invalido; validos: {sorted(validos)}")
    return valor


def _inteiro(valor, campo, minimo=None, maximo=None):
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErroApi(400, f"campo '{campo}' deve ser inteiro")
    if minimo is not None and valor < minimo:
        raise ErroApi(400, f"campo '{campo}' deve ser >= {minimo}")
    if maximo is not None and valor > maximo:
        raise ErroApi(400, f"campo '{campo}' deve ser <= {maximo}")
    return valor


def _numero(valor, campo, minimo=0):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroApi(400, f"campo '{campo}' deve ser numerico")
    if isinstance(valor, float) and not math.isfinite(valor):  # int nunca e NaN/Infinity
        raise ErroApi(400, f"campo '{campo}' deve ser um numero finito")
    if valor < minimo:
        raise ErroApi(400, f"campo '{campo}' deve ser >= {minimo}")
    return valor


def _data_hora(valor, campo):
    if not isinstance(valor, str):
        raise ErroApi(400, f"campo '{campo}' deve ser data/hora ISO-8601")
    try:
        d = datetime.fromisoformat(valor)
    except ValueError as exc:
        raise ErroApi(400, f"campo '{campo}' deve ser data/hora ISO-8601") from exc
    return d.replace(tzinfo=None)


def _data(valor, campo):
    if not isinstance(valor, str):
        raise ErroApi(400, f"campo '{campo}' deve ser data ISO-8601 (AAAA-MM-DD)")
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ErroApi(400, f"campo '{campo}' deve ser data ISO-8601 (AAAA-MM-DD)") from exc


def _int_query(nome, padrao, minimo, maximo=None):
    bruto = request.args.get(nome)
    if bruto is None:
        return padrao
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ErroApi(400, f"parametro '{nome}' deve ser inteiro") from exc
    if valor < minimo or (maximo is not None and valor > maximo):
        faixa = f">= {minimo}" if maximo is None else f"entre {minimo} e {maximo}"
        raise ErroApi(400, f"parametro '{nome}' deve estar {faixa}")
    return valor


def _paginacao():
    return _int_query("limit", LIMIT_PADRAO, 1, LIMIT_MAXIMO), _int_query("offset", 0, 0)


def _listar(tabela, condicoes, params):
    """Lista paginada. 'condicoes' sao fragmentos SQL fixos (com %s); valores vao em 'params'."""
    limit, offset = _paginacao()
    where = f" WHERE {' AND '.join(condicoes)}" if condicoes else ""
    total = db.consultar_um(f"SELECT count(*) AS n FROM {tabela}{where}", params)["n"]
    itens = db.consultar(
        f"SELECT * FROM {tabela}{where} ORDER BY id LIMIT %s OFFSET %s",
        [*params, limit, offset],
    )
    return jsonify({"total": total, "limit": limit, "offset": offset, "itens": itens})


def _obter(tabela, id_):
    linha = db.consultar_um(f"SELECT * FROM {tabela} WHERE id = %s", (id_,))
    if linha is None:
        raise ErroApi(404, "registro nao encontrado")
    return jsonify(linha)


# -------------------------------------------------------------------- rotas

@app.get("/health")
def health():
    try:
        db.consultar_um("SELECT 1 AS ok")
    except Exception:
        return jsonify({"status": "indisponivel", "servico": "dados"}), 503
    return jsonify({"status": "ok", "servico": "dados"})


@app.get("/resumo")
def resumo():
    linha = db.consultar_um(
        "SELECT (SELECT count(*) FROM motoristas) AS motoristas, "
        "(SELECT count(*) FROM veiculos) AS veiculos, "
        "(SELECT count(*) FROM entregas) AS entregas"
    )
    return jsonify(linha)


# Motoristas
@app.get("/motoristas")
def listar_motoristas():
    condicoes, params = [], []
    if request.args.get("cidade_base"):
        condicoes.append("cidade_base = %s")
        params.append(request.args["cidade_base"])
    return _listar("motoristas", condicoes, params)


@app.get("/motoristas/<int:id_>")
def obter_motorista(id_):
    return _obter("motoristas", id_)


@app.post("/motoristas")
def criar_motorista():
    d = _corpo()
    nome = _texto(d, "nome", 100)
    cnh = _opcao(d, "cnh_categoria", CATEGORIAS_CNH)
    cidade = _texto(d, "cidade_base", 60)
    admissao = _data(d.get("data_admissao"), "data_admissao")
    linha = db.executar_retornando(
        "INSERT INTO motoristas (nome, cnh_categoria, cidade_base, data_admissao) "
        "VALUES (%s, %s, %s, %s) RETURNING *",
        (nome, cnh, cidade, admissao),
    )
    return jsonify(linha), 201


# Veiculos
@app.get("/veiculos")
def listar_veiculos():
    condicoes, params = [], []
    if request.args.get("tipo"):
        condicoes.append("tipo = %s")
        params.append(request.args["tipo"])
    return _listar("veiculos", condicoes, params)


@app.get("/veiculos/<int:id_>")
def obter_veiculo(id_):
    return _obter("veiculos", id_)


@app.post("/veiculos")
def criar_veiculo():
    d = _corpo()
    placa = (_texto(d, "placa", 8) or "").upper()
    if not PLACA_RE.match(placa):
        raise ErroApi(400, "campo 'placa' invalido; formato esperado AAA0A00 ou AAA0000")
    tipo = _opcao(d, "tipo", TIPOS_VEICULO)
    capacidade = _inteiro(d.get("capacidade_kg"), "capacidade_kg", minimo=1)
    ano = _inteiro(d.get("ano"), "ano", minimo=1950, maximo=2100)
    try:
        linha = db.executar_retornando(
            "INSERT INTO veiculos (placa, tipo, capacidade_kg, ano) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (placa, tipo, capacidade, ano),
        )
    except errors.UniqueViolation as exc:
        raise ErroApi(409, f"ja existe veiculo com a placa {placa}") from exc
    return jsonify(linha), 201


# Entregas
@app.get("/entregas")
def listar_entregas():
    condicoes, params = [], []
    for campo in ("regiao", "status"):
        if request.args.get(campo):
            condicoes.append(f"{campo} = %s")
            params.append(request.args[campo])
    for campo in ("motorista_id", "veiculo_id"):
        if request.args.get(campo) is not None:
            condicoes.append(f"{campo} = %s")
            params.append(_int_query(campo, None, 1))
    if request.args.get("data_inicio"):
        condicoes.append("data_saida >= %s")
        params.append(_data(request.args["data_inicio"], "data_inicio"))
    if request.args.get("data_fim"):
        # data_fim inclusiva: ate o fim do dia informado
        condicoes.append("data_saida < (%s::date + 1)")
        params.append(_data(request.args["data_fim"], "data_fim"))
    return _listar("entregas", condicoes, params)


@app.get("/entregas/<int:id_>")
def obter_entrega(id_):
    return _obter("entregas", id_)


def _checar_fk(tabela, id_, campo):
    if db.consultar_um(f"SELECT 1 AS ok FROM {tabela} WHERE id = %s", (id_,)) is None:
        raise ErroApi(400, f"{campo} {id_} nao existe")


def _checar_consistencia(status, entregue_em):
    if status == "ENTREGUE" and entregue_em is None:
        raise ErroApi(400, "entregas com status ENTREGUE exigem 'entregue_em'")
    if status != "ENTREGUE" and entregue_em is not None:
        raise ErroApi(400, "'entregue_em' so pode ser informado quando status = ENTREGUE")


@app.post("/entregas")
def criar_entrega():
    d = _corpo()
    motorista_id = _inteiro(d.get("motorista_id"), "motorista_id", minimo=1)
    veiculo_id = _inteiro(d.get("veiculo_id"), "veiculo_id", minimo=1)
    regiao = _opcao(d, "regiao", REGIOES)
    status = _opcao(d, "status", STATUS, obrigatorio=False, padrao="EM_ROTA")
    distancia = _numero(d.get("distancia_km"), "distancia_km")
    custo = _numero(d.get("custo"), "custo")
    peso = _numero(d.get("peso_kg"), "peso_kg")
    if peso <= 0:
        raise ErroApi(400, "campo 'peso_kg' deve ser > 0")
    saida = _data_hora(d.get("data_saida"), "data_saida")
    prazo = _data_hora(d.get("prazo_previsto"), "prazo_previsto")
    entregue = d.get("entregue_em")
    entregue = _data_hora(entregue, "entregue_em") if entregue is not None else None
    _checar_consistencia(status, entregue)
    _checar_fk("motoristas", motorista_id, "motorista_id")
    _checar_fk("veiculos", veiculo_id, "veiculo_id")
    linha = db.executar_retornando(
        "INSERT INTO entregas (motorista_id, veiculo_id, regiao, status, distancia_km, custo, "
        "peso_kg, data_saida, prazo_previsto, entregue_em) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (motorista_id, veiculo_id, regiao, status, distancia, custo, peso, saida, prazo, entregue),
    )
    return jsonify(linha), 201


@app.patch("/entregas/<int:id_>")
def atualizar_entrega(id_):
    d = _corpo()
    permitidos = {"status", "entregue_em", "custo"}
    desconhecidos = set(d) - permitidos
    if desconhecidos or not d:
        raise ErroApi(400, f"informe ao menos um campo atualizavel: {sorted(permitidos)}")
    atual = db.consultar_um("SELECT * FROM entregas WHERE id = %s", (id_,))
    if atual is None:
        raise ErroApi(404, "registro nao encontrado")

    status = _opcao(d, "status", STATUS, obrigatorio=False, padrao=atual["status"])
    if "entregue_em" in d:
        entregue = _data_hora(d["entregue_em"], "entregue_em") if d["entregue_em"] is not None else None
    elif status != "ENTREGUE":
        entregue = None  # mudar para status nao concluido limpa a data de entrega
    else:
        entregue = atual["entregue_em"]
    custo = _numero(d["custo"], "custo") if "custo" in d else atual["custo"]
    _checar_consistencia(status, entregue)

    linha = db.executar_retornando(
        "UPDATE entregas SET status = %s, entregue_em = %s, custo = %s WHERE id = %s RETURNING *",
        (status, entregue, custo, id_),
    )
    return jsonify(linha)
