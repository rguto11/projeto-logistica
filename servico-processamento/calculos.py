"""Calculos puros (sem I/O) sobre listas de entregas.

Regra central: o atraso e DERIVADO. Para entregas com status ENTREGUE,
atraso_min = max(0, entregue_em - prazo_previsto) em minutos. "No prazo"
significa atraso_min == 0. Indicadores de prazo/custo consideram apenas
entregas ENTREGUE.
"""
import statistics
from datetime import datetime

STATUS_CONHECIDOS = ("ENTREGUE", "EM_ROTA", "CANCELADA", "FALHA")
LIMITE_CRITICO_MIN = 120    # atraso (min) a partir do qual a entrega e "critica"
MIN_ENTREGAS_RANKING = 5    # minimo de entregas concluidas para entrar no ranking


def _dt(valor):
    return valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)


def atraso_min(e):
    """Minutos de atraso (>= 0) de uma entrega concluida; None se nao concluida."""
    if e.get("status") != "ENTREGUE" or not e.get("entregue_em"):
        return None
    segundos = (_dt(e["entregue_em"]) - _dt(e["prazo_previsto"])).total_seconds()
    return max(0, int(segundos // 60))


def _pct(parte, total):
    return round(parte / total * 100, 2) if total else 0.0


def _media(valores):
    return round(sum(valores) / len(valores), 2) if valores else 0.0


def _custo_por_km(entregas):
    km = sum(e["distancia_km"] for e in entregas)
    return round(sum(e["custo"] for e in entregas) / km, 2) if km else 0.0


def _concluidas(entregas):
    return [e for e in entregas if e.get("status") == "ENTREGUE"]


def resumo(entregas):
    concluidas = _concluidas(entregas)
    atrasos = [atraso_min(e) for e in concluidas]
    atrasadas = [a for a in atrasos if a > 0]
    por_status = {s: 0 for s in STATUS_CONHECIDOS}
    for e in entregas:
        por_status[e["status"]] = por_status.get(e["status"], 0) + 1
    return {
        "total": len(entregas),
        "por_status": por_status,
        "finalizadas": len(concluidas),
        "no_prazo": len(concluidas) - len(atrasadas),
        "atrasadas": len(atrasadas),
        "pct_no_prazo": _pct(len(concluidas) - len(atrasadas), len(concluidas)),
        "atraso_medio_min": _media(atrasadas),
        "atraso_medio_geral_min": _media(atrasos),
        "atraso_maximo_min": max(atrasos) if atrasos else 0,
        "distancia_total_km": round(sum(e["distancia_km"] for e in concluidas), 2),
        "custo_total": round(sum(e["custo"] for e in concluidas), 2),
        "custo_por_km": _custo_por_km(concluidas),
    }


def por_regiao(entregas):
    grupos = {}
    for e in entregas:
        grupos.setdefault(e["regiao"], []).append(e)
    saida = []
    for regiao, itens in grupos.items():
        concluidas = _concluidas(itens)
        atrasos = [atraso_min(e) for e in concluidas]
        atrasadas = [a for a in atrasos if a > 0]
        saida.append({
            "regiao": regiao,
            "total": len(itens),
            "entregues": len(concluidas),
            "pct_no_prazo": _pct(len(concluidas) - len(atrasadas), len(concluidas)),
            "atraso_medio_min": _media(atrasadas),
            "custo_por_km": _custo_por_km(concluidas),
        })
    return sorted(saida, key=lambda r: (-r["pct_no_prazo"], r["regiao"]))


def ranking_motoristas(entregas, motoristas, top=None, min_entregas=MIN_ENTREGAS_RANKING):
    nomes = {m["id"]: m["nome"] for m in motoristas}
    grupos = {}
    for e in _concluidas(entregas):
        grupos.setdefault(e["motorista_id"], []).append(e)
    linhas = []
    for mid, itens in grupos.items():
        if len(itens) < min_entregas:
            continue
        atrasos = [atraso_min(e) for e in itens]
        atrasadas = [a for a in atrasos if a > 0]
        linhas.append({
            "motorista_id": mid,
            "nome": nomes.get(mid, f"Motorista {mid}"),
            "entregas_finalizadas": len(itens),
            "pct_no_prazo": _pct(len(itens) - len(atrasadas), len(itens)),
            "atraso_medio_min": _media(atrasadas),
            "custo_por_km": _custo_por_km(itens),
            "distancia_total_km": round(sum(e["distancia_km"] for e in itens), 2),
        })
    linhas.sort(key=lambda r: (-r["pct_no_prazo"], r["atraso_medio_min"], r["nome"]))
    if top is not None:
        linhas = linhas[:top]
    for posicao, linha in enumerate(linhas, start=1):
        linha["posicao"] = posicao
    return linhas


def atrasos_criticos(entregas, limite_min=LIMITE_CRITICO_MIN):
    criticos = []
    for e in _concluidas(entregas):
        atraso = atraso_min(e)
        if atraso >= limite_min:
            criticos.append({
                "id": e["id"],
                "motorista_id": e["motorista_id"],
                "regiao": e["regiao"],
                "atraso_min": atraso,
                "prazo_previsto": e["prazo_previsto"],
                "entregue_em": e["entregue_em"],
            })
    return sorted(criticos, key=lambda r: (-r["atraso_min"], r["id"]))


def outliers_custo_km(entregas):
    """Regra do IQR sobre custo/km das entregas concluidas: marca > Q3 + 1,5*IQR."""
    pontos = [
        (e["id"], e["custo"] / e["distancia_km"])
        for e in _concluidas(entregas)
        if e["distancia_km"] > 0
    ]
    if len(pontos) < 4:
        return {"q1": None, "q3": None, "iqr": None, "limite_superior": None,
                "analisadas": len(pontos), "total": 0, "ids": [], "itens": []}
    q1, _, q3 = statistics.quantiles([p[1] for p in pontos], n=4)
    iqr = q3 - q1
    limite = q3 + 1.5 * iqr
    marcados = sorted(((i, v) for i, v in pontos if v > limite), key=lambda p: (-p[1], p[0]))
    return {
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "limite_superior": round(limite, 2),
        "analisadas": len(pontos),
        "total": len(marcados),
        "ids": [i for i, _ in marcados],
        "itens": [{"id": i, "custo_km": round(v, 2)} for i, v in marcados],
    }
