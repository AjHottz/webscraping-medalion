CREATE SCHEMA IF NOT EXISTS prata;

CREATE OR REPLACE VIEW prata.livros AS
WITH dedup AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY TRIM(payload->>'upc') ORDER BY _ingestao_em DESC) as rn -- R1
    FROM bronze.livros
)
SELECT
    TRIM(payload->>'upc') AS upc, -- R7
    TRIM(payload->>'titulo') AS titulo, -- R7
    CASE 
        WHEN TRIM(payload->>'categoria_raw') IN ('Default', 'Add a comment') THEN 'Sem categoria' -- R6
        ELSE TRIM(payload->>'categoria_raw') -- R7
    END AS categoria,
    CAST(SUBSTRING(payload->>'preco_raw' FROM '[0-9]+\.[0-9]+') AS numeric(10,2)) AS preco_gbp, -- R2
    CASE TRIM(payload->>'rating_raw') -- R3
        WHEN 'One' THEN 1
        WHEN 'Two' THEN 2
        WHEN 'Three' THEN 3
        WHEN 'Four' THEN 4
        WHEN 'Five' THEN 5
        ELSE NULL
    END AS rating,
    COALESCE(CAST(SUBSTRING(payload->>'estoque_raw' FROM '[0-9]+') AS int), 0) AS estoque_qtd, -- R4
    CAST(payload->>'n_reviews_raw' AS int) AS n_reviews, -- R5
    TRIM(payload->>'url') AS url, -- R7
    _ingestao_em
FROM dedup
WHERE rn = 1; -- R1
