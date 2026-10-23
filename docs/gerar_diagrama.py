"""Gera docs/diagrama_arquitetura.png (arquitetura de microsserviços)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

DOCS = Path(__file__).resolve().parent
SAIDA = DOCS / "diagrama_arquitetura.png"

COR_SERVICO = "#dbe9f6"
COR_BORDA = "#0b3d66"
COR_DB = "#fde9c9"
COR_CLIENTE = "#e6e6e6"


def caixa(ax, x, y, w, h, titulo, detalhe, cor):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=cor, ec=COR_BORDA, lw=2, zorder=3))
    ax.text(x + w / 2, y + h * 0.66, titulo, ha="center", va="center",
            fontsize=13, fontweight="bold", color="#10202e", zorder=4)
    ax.text(x + w / 2, y + h * 0.28, detalhe, ha="center", va="center",
            fontsize=12, color="#10202e", zorder=4)


def seta(ax, p0, p1, rotulo, pos_rotulo, ha="center"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=22,
                                 lw=2, color="#222222", zorder=2))
    ax.text(*pos_rotulo, rotulo, ha=ha, va="center", fontsize=11, color="#111111", zorder=5,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none"))


fig, ax = plt.subplots(figsize=(10, 6.6), dpi=200)
ax.set_xlim(0, 10)
ax.set_ylim(0, 6.6)
ax.axis("off")

# Moldura do Docker Compose
ax.add_patch(FancyBboxPatch((0.15, 0.2), 9.7, 4.95, boxstyle="round,pad=0.02,rounding_size=0.15",
                            fc="#f7fafc", ec="#4a6b86", lw=2, ls="--", zorder=1))
ax.text(9.65, 4.85, "Docker Compose — rede logistica-net", ha="right", va="center",
        fontsize=13, fontstyle="italic", color="#2c4a63", zorder=2)

caixa(ax, 0.9, 5.65, 2.2, 0.85, "Cliente", "navegador / curl", COR_CLIENTE)
caixa(ax, 0.4, 3.25, 3.1, 1.25, "Serviço de Relatório", "relatorio :8003", COR_SERVICO)
caixa(ax, 6.0, 3.25, 3.6, 1.25, "Serviço de Processamento", "processamento :8002", COR_SERVICO)
caixa(ax, 2.0, 0.65, 3.0, 1.25, "Serviço de Dados", "dados :8001", COR_SERVICO)
caixa(ax, 6.6, 0.65, 2.6, 1.25, "PostgreSQL", "db :5432", COR_DB)

seta(ax, (2.0, 5.65), (2.0, 4.52), "HTTP\nGET /relatorio", (2.15, 5.4), ha="left")
seta(ax, (3.52, 3.88), (5.98, 3.88), "HTTP\nGET /metricas/completo", (4.75, 4.25))
seta(ax, (7.2, 3.23), (4.5, 1.92), "HTTP\nGET /entregas,\n/motoristas", (6.4, 2.6))
seta(ax, (1.7, 3.23), (2.5, 1.92), "HTTP\nGET /resumo", (1.15, 2.55))
seta(ax, (5.02, 1.28), (6.58, 1.28), "SQL", (5.8, 1.62))

fig.savefig(SAIDA, bbox_inches="tight", facecolor="white")
print(f"Gerado: {SAIDA}")

