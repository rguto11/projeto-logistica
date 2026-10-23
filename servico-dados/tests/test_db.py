"""Testes de configuracao e do gerenciador de conexao (pool simulado, sem banco)."""
import psycopg2
import pytest

import db


def test_sem_senha_falha_cedo(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        db.parametros_conexao()


def test_com_senha_usa_defaults_dos_demais_parametros(monkeypatch):
    for var in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DB_PASSWORD", "x")
    parametros = db.parametros_conexao()
    assert parametros["password"] == "x"
    assert parametros["host"] == "db"
    assert parametros["port"] == 5432


class FakeConn:
    def __init__(self, erro_no_rollback=None):
        self.eventos = []
        self._erro_no_rollback = erro_no_rollback

    def commit(self):
        self.eventos.append("commit")

    def rollback(self):
        self.eventos.append("rollback")
        if self._erro_no_rollback:
            raise self._erro_no_rollback


class FakePool:
    def __init__(self, conn):
        self.conn = conn
        self.devolvidas = []

    def getconn(self):
        return self.conn

    def putconn(self, conn):
        self.devolvidas.append(conn)


def _pool(monkeypatch, conn):
    pool = FakePool(conn)
    monkeypatch.setattr(db, "_obter_pool", lambda: pool)
    return pool


def test_conexao_sucesso_faz_commit_e_devolve_ao_pool(monkeypatch):
    conn = FakeConn()
    pool = _pool(monkeypatch, conn)
    with db.conexao():
        pass
    assert conn.eventos == ["commit"]
    assert pool.devolvidas == [conn]


def test_conexao_com_erro_faz_rollback_e_propaga(monkeypatch):
    conn = FakeConn()
    pool = _pool(monkeypatch, conn)
    with pytest.raises(ValueError, match="boom"), db.conexao():
        raise ValueError("boom")
    assert conn.eventos == ["rollback"]
    assert pool.devolvidas == [conn]


def test_rollback_que_falha_nao_mascara_o_erro_original(monkeypatch):
    conn = FakeConn(erro_no_rollback=psycopg2.InterfaceError("conexao morta"))
    pool = _pool(monkeypatch, conn)
    with pytest.raises(ValueError, match="boom"), db.conexao():
        raise ValueError("boom")
    assert conn.eventos == ["rollback"]
    assert pool.devolvidas == [conn]
