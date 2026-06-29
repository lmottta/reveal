# Specs do Projeto — Reveal (JuriPopular)

## 1. Stack Tecnológica

| Camada      | Tecnologia                                              |
|-------------|--------------------------------------------------------|
| Backend     | Python 3.10+, FastAPI, Uvicorn                          |
| ORM         | SQLAlchemy 2.0 + psycopg2-binary (PostgreSQL)           |
| RPA Engine  | Playwright (Python) + BeautifulSoup4 + lxml             |
| CAPTCHA     | Tesseract OCR (local) + 2Captcha/anti-captcha (opcional)|
| Frontend    | HTML5, CSS3 (variáveis), JavaScript ES6+, Leaflet.js    |
| Mapas       | Leaflet 1.x + OpenStreetMap tiles                       |
| Deploy      | Docker, Railway, Vercel                                 |
| Infra       | docker-compose (PostgreSQL 15 + backend)                |
| Banco Local | SQLite (fallback para dev sem Docker)                   |
| IDE         | OpenCode (recomendado)                                  |

## 2. Dependências Core (requirements.txt)

```
fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings
python-dotenv, requests, httpx, python-multipart
playwright, beautifulsoup4, lxml
httpx, psycopg2-binary, pytesseract, Pillow, duckduckgo_search
```

## 3. Endpoints da API

### Prefixo: `/api/v1`

#### Search
- `GET /api/v1/search/?q=&state=&page=&per_page=`
- `GET /api/v1/search/catalog/?state=&page=&per_page=`
- `GET /api/v1/search/analyze/?id=`

#### Stats
- `GET /api/v1/stats/kpi/?state=`
- `GET /api/v1/stats/geo/?state=`
- `GET /api/v1/stats/ufs/{uf}/cities/`

#### Health
- `GET /health`
- `GET /api/v1/diagnostics`

## 4. Modelos de Dados

### Lawsuit
```sql
CREATE TABLE lawsuits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnj_number VARCHAR(25) UNIQUE,
    class_ CNV VARCHAR(100),
    subject VARCHAR(200),
    distribution_date DATE,
    court VARCHAR(100),
    judge VARCHAR(200),
    action_type VARCHAR(100),
    parties TEXT,       -- JSON string
    movements TEXT,     -- JSON string
    state VARCHAR(2),
    tribunal VARCHAR(10),
    city VARCHAR(100),
    last_movement_date DATE,
    first_instance_result VARCHAR(200),
    second_instance_result VARCHAR(200),
    updated_in TRIBUNAL BOOLEAN DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### News
```sql
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500),
    url VARCHAR(1000) UNIQUE,
    source VARCHAR(200),
    snippet TEXT,
    published_date DATE,
    search_term VARCHAR(200),
    state VARCHAR(2),
    city VARCHAR(100),
    relevance_score FLOAT,
    is_relevant BOOLEAN DEFAULT 0,
    created_at TIMESTAMP
);
```

### SearchResult
```sql
CREATE TABLE search_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER REFERENCES searches(id),
    content TEXT,        -- JSON string
    type VARCHAR(50),    -- 'news', 'lawsuit', 'web'
    source VARCHAR(200),
    relevance FLOAT,
    created_at TIMESTAMP
);
```

### Search
```sql
CREATE TABLE searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query VARCHAR(500),
    state VARCHAR(2),
    results_count INTEGER,
    created_at TIMESTAMP
);
```

## 5. Keywords de Relevância (Crimes Sexuais)

```
ESTUPRO, ABUSO SEXUAL, PEDOFILIA, TRÁFICO SEXUAL, EXPLORAÇÃO SEXUAL,
VIOLÊNCIA SEXUAL, ASSÉDIO SEXUAL, IMPORTUNAÇÃO SEXUAL, CORRUPÇÃO DE MENORES,
SATISFAÇÃO DE LASCÍVIA, ATO LIBIDINOSO, CRIANÇA, ADOLESCENTE, MENOR,
VULNERÁVEL, STALKING, PORNOGRAFIA, ALICIAMENTO, SEXTING, VIOLAÇÃO,
REGISTRO NÃO AUTORIZADO, DIVULGAÇÃO DE CENA
```

## 6. Mapeamento Tribunal → Sistema RPA

| Código | Tribunal | Sistema RPA    |
|--------|----------|----------------|
| 01     | TJAC     | esaj           |
| 02     | TJAL     | esaj           |
| 03     | TJAM     | esaj           |
| 04     | TJAP     | tucujuris      |
| 05     | TJBA     | pje            |
| 06     | TJCE     | esaj           |
| 07     | TJDF     | pje            |
| 08     | TJES     | pje            |
| 09     | TJGO     | projudi        |
| 10     | TJMA     | pje            |
| 11     | TJMT     | pje            |
| 12     | TJMS     | esaj           |
| 13     | TJMG     | pje            |
| 14     | TJPA     | pje            |
| 15     | TJPB     | pje            |
| 16     | TJPR     | projudi        |
| 17     | TJPE     | pje            |
| 18     | TJPI     | pje            |
| 19     | TJRN     | pje            |
| 20     | TJRS     | eproc          |
| 21     | TJRO     | pje            |
| 22     | TJRR     | projudi        |
| 23     | TJSC     | eproc          |
| 24     | TJSP     | esaj           |
| 25     | TJSE     | pje            |
| 26     | TJTO     | eproc          |
| 27     | TJRJ     | tjrj (custom)  |

## 7. Regras de Deduplicação

1. **Nível 1 - URL Exata**: Normalizar (lowercase protocol+host, remover UTM params, trailing slashes)
2. **Nível 2 - Fuzzy Title**: SequenceMatcher similarity > 85%
3. **Nível 3 - Contextual**: Similarity > 60% + snippet idêntico

## 8. Configuração de Deploy

### Docker (Railway)
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy
# Instala Tesseract OCR + Python deps + Playwright Chromium
CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Variáveis de Ambiente
```
# PostgreSQL via Docker
DATABASE_URL=postgresql://reveal_user:reveal_password@localhost:5432/reveal_db

# Opção alternativa: variáveis individuais
POSTGRES_SERVER=localhost
POSTGRES_USER=reveal_user
POSTGRES_PASSWORD=reveal_password
POSTGRES_DB=reveal_db

# SQLite (dev sem Docker)
# DATABASE_URL=sqlite:///reveal.db

CAPTCHA_API_KEY=2captcha_key_optional
```

## 9. Testes

```bash
# Unitários
cd backend && python -m pytest tests/ -v

# Sistema (custom)
python scripts/test_system.py

# E2E (backend rodando)
python scripts/e2e_test.py
```

## 10. Roadmap

- [x] MVP: busca básica + notícias
- [x] PostgreSQL com Docker
- [x] Deduplicação avançada
- [x] Coleta em massa
- [ ] Exportação de relatórios (PDF/CSV)
- [ ] Alertas de monitoramento
- [ ] Expansão para Tribunais Federais (TRF)
- [ ] Análise de grafo de relacionamentos
