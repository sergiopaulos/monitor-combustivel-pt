-- Corre este SQL no Supabase SQL Editor para criar a tabela

CREATE TABLE IF NOT EXISTS precos_combustivel (
    id              BIGSERIAL PRIMARY KEY,
    data            DATE NOT NULL,
    distrito        TEXT NOT NULL,
    municipio       TEXT,
    nome_posto      TEXT,
    tipo_combustivel TEXT NOT NULL,
    preco           NUMERIC(6, 3) NOT NULL,
    marca           TEXT,
    criado_em       TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para queries rápidas
CREATE INDEX IF NOT EXISTS idx_data        ON precos_combustivel (data);
CREATE INDEX IF NOT EXISTS idx_distrito    ON precos_combustivel (distrito);
CREATE INDEX IF NOT EXISTS idx_tipo        ON precos_combustivel (tipo_combustivel);

-- Evita duplicados para o mesmo posto/dia/combustível
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_registo
    ON precos_combustivel (data, nome_posto, tipo_combustivel);
