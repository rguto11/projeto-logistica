-- Esquema do Servico de Dados (idempotente).
-- Timestamps sao "naive" (sem fuso) e serializados em ISO-8601 pela API.
-- Obs.: CREATE TABLE IF NOT EXISTS nao altera tabelas ja criadas; a restricao em peso_kg
-- so vale em banco novo (docker compose down -v).

CREATE TABLE IF NOT EXISTS motoristas (
    id            SERIAL PRIMARY KEY,
    nome          VARCHAR(100) NOT NULL,
    cnh_categoria VARCHAR(3)   NOT NULL,
    cidade_base   VARCHAR(60)  NOT NULL,
    data_admissao DATE         NOT NULL
);

CREATE TABLE IF NOT EXISTS veiculos (
    id            SERIAL PRIMARY KEY,
    placa         VARCHAR(8)  UNIQUE NOT NULL,
    tipo          VARCHAR(20) NOT NULL,  -- MOTO, VAN, CAMINHAO_LEVE, CAMINHAO
    capacidade_kg INT         NOT NULL CHECK (capacidade_kg > 0),
    ano           INT         NOT NULL
);

CREATE TABLE IF NOT EXISTS entregas (
    id             SERIAL PRIMARY KEY,
    motorista_id   INT           NOT NULL REFERENCES motoristas(id),
    veiculo_id     INT           NOT NULL REFERENCES veiculos(id),
    regiao         VARCHAR(30)   NOT NULL,  -- Centro, Zona Norte, Zona Sul, Zona Leste, Zona Oeste
    status         VARCHAR(12)   NOT NULL CHECK (status IN ('ENTREGUE','EM_ROTA','CANCELADA','FALHA')),
    distancia_km   NUMERIC(8,2)  NOT NULL CHECK (distancia_km >= 0),
    custo          NUMERIC(10,2) NOT NULL CHECK (custo >= 0),
    peso_kg        NUMERIC(8,2)  NOT NULL CHECK (peso_kg > 0),
    data_saida     TIMESTAMP     NOT NULL,
    prazo_previsto TIMESTAMP     NOT NULL,
    entregue_em    TIMESTAMP     NULL  -- NULL, exceto quando status = 'ENTREGUE'
);

CREATE INDEX IF NOT EXISTS idx_entregas_regiao       ON entregas (regiao);
CREATE INDEX IF NOT EXISTS idx_entregas_status       ON entregas (status);
CREATE INDEX IF NOT EXISTS idx_entregas_motorista_id ON entregas (motorista_id);
CREATE INDEX IF NOT EXISTS idx_entregas_data_saida   ON entregas (data_saida);
