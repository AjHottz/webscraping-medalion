CREATE SCHEMA IF NOT EXISTS ouro;

CREATE OR REPLACE VIEW ouro.livros AS
SELECT
    *,
    (preco_gbp * estoque_qtd) AS valor_estoque_gbp, -- M1
    CASE -- M3
        WHEN preco_gbp < 20 THEN 'até £20'
        WHEN preco_gbp >= 20 AND preco_gbp < 40 THEN '£20–40'
        WHEN preco_gbp >= 40 THEN 'acima de £40'
    END AS faixa_preco,
    (rating >= 4) AS bem_avaliado -- M2
FROM prata.livros;

CREATE OR REPLACE VIEW ouro.categorias AS
SELECT
    categoria,
    COUNT(*) AS qtd_titulos,
    ROUND(AVG(preco_gbp), 2) AS preco_medio_gbp,
    ROUND(AVG(rating), 2) AS rating_medio,
    SUM(estoque_qtd) AS estoque_unidades,
    SUM(preco_gbp * estoque_qtd) AS valor_estoque_gbp,
    ROUND(COUNT(CASE WHEN rating >= 4 THEN 1 END) * 100.0 / COUNT(*), 2) AS pct_bem_avaliados
FROM prata.livros
GROUP BY categoria;
