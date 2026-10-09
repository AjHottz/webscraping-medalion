CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.livros (
    id bigserial PRIMARY KEY,
    fonte_url text NOT NULL,
    payload jsonb NOT NULL,
    _execucao_id text NOT NULL,
    _ingestao_em timestamptz DEFAULT now()
);
