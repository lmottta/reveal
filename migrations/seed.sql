-- Dados de seed para desenvolvimento local
-- Insere apenas se as tabelas estiverem vazias

INSERT INTO search (query, tribunal, created_at)
SELECT 'estupro', 'TJSP', NOW()
WHERE NOT EXISTS (SELECT 1 FROM search LIMIT 1);

INSERT INTO news (title, url, source, snippet, published_date, state, city, is_relevant)
SELECT
    'Operação policial prende suspeito de estupro em São Paulo',
    'https://g1.globo.com/sp/exemplo-1',
    'G1',
    'Policiais civis prenderam um homem suspeito de cometer estupro na zona norte da capital paulista.',
    '2026-03-20',
    'SP',
    'São Paulo',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM news LIMIT 1);
