"""Gera os gráficos de resultados a partir de docs/evidencias/relatorio.json."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DOCS = Path(__file__).resolve().parent
ENTRADA = DOCS / "evidencias" / "relatorio.json"

if not ENTRADA.exists():
    sys.exit(f"Evidência ausente: {ENTRADA}. Execute a pilha e capture o relatório antes.")

dados = json.loads(ENTRADA.read_text(encoding="utf-8"))
ind = dados["indicadores"]


def fmt(v, casas=2):
    return f"{v:.{casas}f}".replace(".", ",")


AZUL, LARANJA, VERDE, CINZA = "#0b5394", "#c55a11", "#2e7d32", "#555555"


def salvar(fig, nome):
    caminho = DOCS / nome
    fig.savefig(caminho, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Gerado: {caminho}")


# 1) % no prazo por região
regioes = ind["regioes"]
geral = ind["resumo"]["pct_no_prazo"]
fig, ax = plt.subplots(figsize=(7, 4))
nomes = [r["regiao"] for r in regioes]
vals = [r["pct_no_prazo"] for r in regioes]
barras = ax.bar(nomes, vals, color=AZUL, width=0.6)
for b, v in zip(barras, vals):
    ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{fmt(v)}%", ha="center", fontsize=11)
ax.axhline(geral, color=LARANJA, ls="--", lw=2, label=f"Média geral: {fmt(geral)}%")
ax.set_ylim(0, 105)
ax.set_ylabel("Entregas no prazo (%)", fontsize=12)
ax.set_xlabel("Região", fontsize=12)
ax.set_title("Pontualidade por região", fontsize=14)
ax.tick_params(labelsize=11)
ax.legend(loc="upper right", fontsize=11)
ax.spines[["top", "right"]].set_visible(False)
salvar(fig, "grafico_regioes.png")

# 2) Entregas por status
status = ind["status"]
ordem = ["ENTREGUE", "EM_ROTA", "FALHA", "CANCELADA"]
rotulos = {"ENTREGUE": "Entregue", "EM_ROTA": "Em rota", "FALHA": "Falha", "CANCELADA": "Cancelada"}
cores = {"ENTREGUE": VERDE, "EM_ROTA": AZUL, "FALHA": LARANJA, "CANCELADA": CINZA}
fig, ax = plt.subplots(figsize=(7, 4))
chaves = [k for k in ordem if k in status]
valores = [status[k] for k in chaves]
barras = ax.bar([rotulos[k] for k in chaves], valores, color=[cores[k] for k in chaves], width=0.6)
for b, v in zip(barras, valores):
    ax.text(b.get_x() + b.get_width() / 2, v + max(valores) * 0.015, str(v), ha="center", fontsize=11)
ax.set_ylim(0, max(valores) * 1.12)
ax.set_ylabel("Quantidade de entregas", fontsize=12)
ax.set_xlabel("Status", fontsize=12)
ax.set_title(f"Entregas por status (total: {ind['resumo']['total']})", fontsize=14)
ax.tick_params(labelsize=11)
ax.spines[["top", "right"]].set_visible(False)
salvar(fig, "grafico_status.png")

# 3) Ranking top 10 motoristas
rank = ind["ranking_motoristas"]
fig, ax = plt.subplots(figsize=(7, 4.6))
nomes = [f"{r['posicao']}. {r['nome']}" for r in rank][::-1]
vals = [r["pct_no_prazo"] for r in rank][::-1]
barras = ax.barh(nomes, vals, color=AZUL, height=0.65)
for b, v in zip(barras, vals):
    ax.text(v + 1, b.get_y() + b.get_height() / 2, f"{fmt(v)}%", va="center", fontsize=10)
ax.set_xlim(0, 112)
ax.set_xlabel("Entregas no prazo (%)", fontsize=12)
ax.set_title("Top 10 motoristas por pontualidade", fontsize=14)
ax.tick_params(labelsize=10)
ax.spines[["top", "right"]].set_visible(False)
salvar(fig, "grafico_ranking.png")

