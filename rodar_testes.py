"""Roda os testes dos tres servicos com um unico comando: python rodar_testes.py [args do pytest].

O pytest e executado uma vez por servico (cada um com seu pytest.ini) porque os
servicos tem modulos homonimos (app, db) que colidiriam em uma unica sessao.
Sai com 0 somente se todos os servicos passarem.
"""
import subprocess
import sys
from pathlib import Path

SERVICOS = ("servico-dados", "servico-processamento", "servico-relatorio")


def main():
    raiz = Path(__file__).parent
    resultados = {}
    for servico in SERVICOS:
        print(f"=== {servico} ===", flush=True)
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], cwd=raiz / servico)
        resultados[servico] = proc.returncode
    print("\n=== Resumo ===")
    for servico, codigo in resultados.items():
        print(f"{servico}: {'OK' if codigo == 0 else f'FALHOU (codigo {codigo})'}")
    return 0 if all(c == 0 for c in resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
