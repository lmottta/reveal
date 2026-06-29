# Contexto do Projeto — Reveal (JuriPopular)

## Identidade
- **Nome:** Reveal (nome fantasia: JuriPopular)
- **Propósito:** Plataforma de Inteligência e Investigação Assistida para monitoramento de crimes sexuais e corrupção no Brasil
- **Stack:** Python 3.10+ / FastAPI / PostgreSQL (Docker) / SQLite (fallback) / Playwright / HTML+CSS+JS vanilla / Leaflet.js CDN

## Estrutura do Projeto

```
reveal/
├── backend/
│   ├── main.py                  # FastAPI entry point (init_db no startup)
│   ├── requirements.txt         # Python dependencies
│   ├── reveal.db                # SQLite database legacy (3.4MB)
│   ├── .env                     # DATABASE_URL
│   ├── .env.example             # Template
│   ├── app/
│   │   ├── api/
│   │   │   ├── api.py           # Router aggregation (/api/v1)
│   │   │   └── endpoints/
│   │   │       ├── search.py    # Search + catalog + scan endpoints
│   │   │       └── stats.py     # KPI + geo + cities endpoints
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings (DATABASE_URL)
│   │   │   ├── constants.py     # CNJ map, keywords, coordinates
│   │   │   ├── captcha_solver.py# OCR + 2Captcha
│   │   │   └── utils.py         # CNJ validation (mod 97)
│   │   ├── db/
│   │   │   ├── base.py          # Model imports
│   │   │   ├── base_class.py    # SQLAlchemy Base
│   │   │   ├── init_db.py       # create_all() on startup
│   │   │   └── session.py       # Engine + SessionLocal
│   │   ├── middleware/
│   │   │   └── __init__.py      # (empty)
│   │   ├── models/
│   │   │   ├── search.py        # Search, SearchResult, News
│   │   │   └── lawsuit.py       # Lawsuit
│   │   └── rpa/
│   │       ├── base.py          # Abstract RPA
│   │       ├── config.py        # Tribunal -> RPA system mapper
│   │       ├── google_news.py   # Google News scraper
│   │       ├── google_web.py    # DuckDuckGo/Google scraper
│   │       ├── news_aggregator.py # 14 Brazilian news sources
│   │       ├── tjmt.py          # TJMT custom RPA
│   │       ├── tjrj.py          # TJRJ custom RPA
│   │       ├── tjsp.py          # TJSP custom RPA
│   │       └── systems/
│   │           ├── base_system.py
│   │           ├── eproc.py     # RS, SC, TO
│   │           ├── esaj.py      # SP, AC, AL, AM, MS, CE
│   │           ├── pje.py       # BA, MG, MT, DF, ES, MA, PA, PB, PE, PI, RN, RO, RR, SE, AP
│   │           ├── projudi.py   # PR, GO, RR
│   │           └── tucujuris.py # AP
│   ├── static/
│   │   ├── index.html           # SPA (Leaflet via CDN)
│   │   ├── favicon.ico
│   │   └── img/background.png
│   └── tests/
│       ├── conftest.py          # SQLite para testes
│       ├── test_consistency.py  # City/geo/parties/catalog
│       └── test_validation.py   # CNJ validation
├── scripts/
│   ├── aaron_hunter.py          # Target hunting from news
│   ├── e2e_test.py              # End-to-end test
│   ├── fetch_news_as_lawsuits.py
│   ├── fetch_real_lawsuits.py   # Demo data
│   ├── fetch_real_names_lawsuits.py
│   ├── inject_mock_lawsuits.py  # Mock data
│   ├── mass_collection_v2.py    # Mass news collector
│   ├── populate_lawsuits.py     # RPA lawsuit population
│   ├── populate_targets.py      # Target extraction
│   └── test_system.py           # System test suite
├── migrations/
│   ├── init.sql                 # PostgreSQL schema (Docker)
│   └── seed.sql                 # Seed data
├── Dockerfile
├── docker-compose.yml           # PostgreSQL 15 + backend
├── railway.json
├── vercel.json
└── .gitignore
```

## Arquitetura

```
Frontend (SPA)  ←→  FastAPI  ←→  PostgreSQL (Docker)
                    ↕
              RPA Engine (Playwright)
                    ↕
       27 Tribunais + 14 Portais de Notícias
```

## Decisões Arquiteturais

1. **PostgreSQL + SQLite**: PostgreSQL via Docker, SQLite fallback, configurável via `DATABASE_URL`
2. **DB Init automático**: `init_db()` no startup via `Base.metadata.create_all()`
3. **RPA por sistema**: Agrupado por sistema judiciário (PJe, e-SAJ, Eproc, Projudi, Tucujuris)
4. **Deduplicação 3 níveis**: URL exata → fuzzy title (>85%) → contextual (>60% + snippet)
5. **Stealth RPA**: Playwright headless, User-Agent custom, delays aleatórios, anti-detection
6. **CAPTCHA**: OCR Tesseract local + fallback 2Captcha
7. **Leaflet via CDN**: Carregado de unpkg.com, sem vendor local

## Regras de Negócio

### Filtragem
- 22 keywords (ESTUPRO, ABUSO SEXUAL, PEDOFILIA, TRÁFICO SEXUAL...)
- Case-insensitive + normalização Unicode

### CNJ
- Formato: `NNNNNNN-DD.AAAA.J.TR.OOOO`
- Dígitos verificadores: Mod 97 base 10
- Estado inferido do código do tribunal (posições 14-16)

### Privacidade (LGPD)
- Dados judiciais = BI anônimo (estatísticas, sem nomes expostos)
- Catálogo de indivíduos é controlado e estruturado

### Ética RPA
- Apenas portais públicos sem login
- Sem download em massa, sem bypass de CAPTCHA (exceto OCR)
- Sem busca por CPF, sem classificação criminal

## Comandos

```bash
docker compose up --build           # Docker (PostgreSQL + backend)
docker compose down -v              # Parar + limpar volumes
cd backend; $env:DATABASE_URL="sqlite:///reveal.db"; python -m uvicorn main:app --reload --port 8000
cd backend; $env:DATABASE_URL="sqlite:///./test_reveal.db"; python -m pytest tests/ -v
```

## Estado Atual
- Branch: `master` | 68 arquivos rastreados
- MVP completo: busca, RPA judicial, agregação de notícias, dashboard BI
- Deploy: Railway (Docker) / Vercel

## Tech Debt
1. Pydantic V2: `@validator` → `@field_validator` em `config.py`
2. SQLAlchemy 2.0: `as_declarative()` → `sqlalchemy.orm.as_declarative()`
3. `datetime.utcnow()` → `datetime.now(datetime.UTC)`
4. Python 3.14: falta `from __future__ import annotations`
