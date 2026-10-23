"""Prepara o banco antes do gunicorn: aguarda o PostgreSQL, aplica o esquema e
popula os dados sinteticos somente se a tabela motoristas estiver vazia."""
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

import db
from seed import gerar_dados

TENTATIVAS = 30
INTERVALO_S = 2


def aguardar_banco():
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            conn = db.conexao_unica()
            print(f"[init_db] conexao com o banco OK (tentativa {tentativa})", flush=True)
            return conn
        except psycopg2.OperationalError as exc:
            print(f"[init_db] banco indisponivel (tentativa {tentativa}/{TENTATIVAS}): {exc}".strip(), flush=True)
            time.sleep(INTERVALO_S)
    print("[init_db] tempo esgotado aguardando o banco", flush=True)
    sys.exit(1)


def main():
    conn = aguardar_banco()
    try:
        # uma unica transacao: esquema + carga
        with conn, conn.cursor() as cur:
            cur.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
            cur.execute("SELECT count(*) FROM motoristas")
            if cur.fetchone()[0] > 0:
                print("[init_db] banco ja populado; seed ignorado", flush=True)
                return

            dados = gerar_dados()
            ids_motoristas = [
                r[0] for r in execute_values(
                    cur,
                    "INSERT INTO motoristas (nome, cnh_categoria, cidade_base, data_admissao) "
                    "VALUES %s RETURNING id",
                    dados["motoristas"], page_size=1000, fetch=True)
            ]
            ids_veiculos = [
                r[0] for r in execute_values(
                    cur,
                    "INSERT INTO veiculos (placa, tipo, capacidade_kg, ano) VALUES %s RETURNING id",
                    dados["veiculos"], page_size=1000, fetch=True)
            ]
            linhas = [
                (ids_motoristas[e[0]], ids_veiculos[e[1]], *e[2:])
                for e in dados["entregas"]
            ]
            execute_values(
                cur,
                "INSERT INTO entregas (motorista_id, veiculo_id, regiao, status, distancia_km, "
                "custo, peso_kg, data_saida, prazo_previsto, entregue_em) VALUES %s",
                linhas, page_size=1000)
            print(
                f"[init_db] seed aplicado: {len(ids_motoristas)} motoristas, "
                f"{len(ids_veiculos)} veiculos, {len(linhas)} entregas",
                flush=True,
            )
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"[init_db] {exc}", flush=True)
        sys.exit(1)
