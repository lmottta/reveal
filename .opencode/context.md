# Contexto do Projeto — Reveal (JuriPopular)

## Identidade
- **Nome:** Reveal (nome fantasia: JuriPopular)
- **Propósito:** Plataforma de Inteligência e Investigação Assistida para monitoramento de crimes sexuais e corrupção no Brasil
- **Stack:** Python 3.10+ / FastAPI / PostgreSQL (Docker) / SQLite (fallback) / Playwright / HTML+CSS+JS vanilla / Leaflet.js

## Estrutura do Projeto

```
reveal/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── requirements.txt         # Python dependencies
│   ├── reveal.db                # SQLite database (3.4MB, mantido)
│   ├── .env                     # SQLite connection string
│   ├── .env.example             # Template com todas as env vars
│   ├── app/
│   │   ├── api/
│   │   │   ├── api.py           # Router aggregation (/api/v1)
│   │   │   └── endpoints/
│   │   │       ├── search.py          # Search endpoint (SQLite)
│   │   │       ├── search_supabase.py # Search endpoint (Supabase)
│   │   │       ├── stats.py           # Statistics endpoint (SQLite)
│   │   │       └── stats_supabase.py  # Statistics endpoint (Supabase)
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings
│   │   │   ├── constants.py     # CNJ map, keywords, coordinates
│   │   │   ├── supabase.py      # Supabase client init
│   │   │   ├── supabase_lite.py # Lightweight Supabase REST client
│   │   │   ├── captcha_solver.py# OCR + 2Captcha CAPTCHA solver
│   │   │   └── utils.py         # CNJ validation (mod 97)
│   │   ├── db/
│   │   │   ├── base.py          # Model imports
│   │   │   ├── base_class.py    # SQLAlchemy Base
│   │   │   ├── init_db.py       # Table creation
│   │   │   └── session.py       # Session factory
│   │   ├── middleware/
│   │   │   └── auth.py          # Supabase JWT auth
│   │   ├── models/
│   │   │   ├── search.py        # Search, SearchResult, News
│   │   │   └── lawsuit.py       # Lawsuit
│   │   ├── rpa/
│   │   │   ├── base.py          # Abstract RPA
│   │   │   ├── config.py        # Tribunal -> RPA mapper
│   │   │   ├── google_news.py   # Google News scraper
│   │   │   ├── google_web.py    # DuckDuckGo/Google scraper
│   │   │   ├── news_aggregator.py # 14 sources aggregator
│   │   │   ├── tjmt.py          # TJMT custom RPA
│   │   │   ├── tjrj.py          # TJRJ custom RPA
│   │   │   ├── tjsp.py          # TJSP custom RPA
│   │   │   └── systems/
│   │   │       ├── base_system.py   # Abstract system RPA
│   │   │       ├── eproc.py         # Eproc (RS, SC, TO)
│   │   │       ├── esaj.py          # e-SAJ (SP, AC, AL, AM, MS, CE)
│   │   │       ├── pje.py           # PJe (BA, MG, MT, etc.)
│   │   │       ├── projudi.py       # Projudi (PR, GO, RR)
│   │   │       └── tucujuris.py     # Tucujuris (AP)
│   │   └── schemas/             # (vazio, não utilizado)
│   ├── scripts/
│   │   ├── queries.sql          # SQL query examples
│   │   ├── query_geral.py       # DB dump
│   │   └── validate_supabase.py # Supabase validator
│   ├── static/
│   │   ├── index.html           # SPA principal (1872 linhas)
│   │   ├── favicon.ico
│   │   ├── img/background.png
│   │   └── vendor/leaflet/      # Leaflet 1.x
│   └── tests/
│       ├── test_consistency.py  # Unit: city/geo/parties
│       └── test_validation.py   # Unit: CNJ validation
├── scripts/
│   ├── aaron_hunter.py             # Target hunting from news
│   ├── clean_supabase_duplicates.py# Dedup Supabase
│   ├── e2e_test.py                 # End-to-end test
│   ├── fetch_news_as_lawsuits.py   # News -> Lawsuit extraction
│   ├── fetch_real_lawsuits.py      # Demo lawsuit data
│   ├── fetch_real_names_lawsuits.py# Name-based lawsuit search
│   ├── generate_favicon.py         # Favicon generator
│   ├── inject_mock_lawsuits.py     # Mock data injection
│   ├── mass_collection.py          # Legacy mass collector
│   ├── mass_collection_v2.py       # Mass collector v2
│   ├── populate_lawsuits.py        # Lawsuit population from RPA
│   ├── populate_targets.py         # Target extraction
│   └── test_system.py              # System test suite
├── migrations/
│   ├── init.sql                    # Schema SQL para Docker
│   └── seed.sql                    # Seed data para Docker
├── docs/PRD.md                     # Product Requirements Document
├── .opencode/                      # OpenCode project config
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── vercel.json
└── .gitignore
```

## Arquitetura

```ascii
Frontend (index.html SPA)  ←→  FastAPI Backend  ←→  PostgreSQL (Docker) / SQLite
                                    ↕
                              RPA Engine (Playwright)
                                    ↕
                        27 Tribunais + 14 Portais de Notícias
```

## Decisões Arquiteturais (ADRs)

1. **PostgreSQL + SQLite**: PostgreSQL via Docker (produção/dev) com fallback SQLite para desenvolvimento sem Docker. Database URL configurável via `DATABASE_URL` no `.env`.
2. **DB Init automático**: `init_db()` roda no startup do FastAPI via `Base.metadata.create_all()`.
2. **RPA por sistema judiciário**: Em vez de um RPA por tribunal, agrupa-se por sistema (PJe, e-SAJ, Eproc, Projudi, Tucujuris) que atende múltiplos estados.
3. **Deduplicação em 3 níveis**: URL exata → fuzzy title (>85%) → contextual (>60% + snippet).
4. **Stealth RPA**: Playwright headless com User-Agent customizado, delays aleatórios, anti-detection scripts.
5. **CAPTCHA handling**: OCR local (Tesseract) com fallback opcional para 2Captcha/anti-captcha.

## Regras de Negócio

### Filtragem de Relevância
- Conteúdo deve conter ao menos 1 dos 22 keywords portugueses (ESTUPRO, ABUSO SEXUAL, PEDOFILIA, TRÁFICO SEXUAL, etc.)
- Matching case-insensitive com normalização Unicode

### Validação CNJ
- Formato: `NNNNNNN-DD.AAAA.J.TR.OOOO`
- Dígitos verificadores: Mod 97 base 10
- Inferência de estado a partir do código do tribunal (posições 14-16)

### Mapeamento Tribunal → Sistema
- 01=TJAC, 02=TJAL, ..., 27=TJTO
- Cada um mapeado para: PJe, e-SAJ, Eproc, Projudi, Tucujuris, ou custom

### Privacidade (LGPD)
- Dados judiciais são tratados como BI anônimo (estatísticas agregadas)
- Nomes de partes e juízes NÃO são expostos na interface final
- Catálogo de indivíduos é controlado e estruturado

### Ética RPA
- Apenas portais públicos sem login
- Sem download em massa
- Sem bypass de CAPTCHA (exceto OCR local)
- Sem busca por CPF
- Sem classificação criminal de indivíduos
- Uso exclusivo para conformidade institucional

## Comandos Úteis

```bash
# Iniciar Docker (PostgreSQL + Backend) - RECOMENDADO
docker compose up --build

# Parar Docker e limpar volumes
docker compose down -v

# Iniciar backend local (modo SQLite - sem Docker)
cd backend
$env:DATABASE_URL="sqlite:///reveal.db"
python -m uvicorn main:app --reload --port 8000

# Iniciar backend local (modo PostgreSQL - com Docker db rodando)
cd backend
$env:DATABASE_URL="postgresql://reveal_user:reveal_password@localhost:5432/reveal_db"
python -m uvicorn main:app --reload --port 8000

# Testes unitários (usa SQLite)
cd backend; $env:DATABASE_URL="sqlite:///./test_reveal.db"; python -m pytest tests/ -v

# Teste de sistema
python scripts/test_system.py

# E2E test (requer backend rodando)
python scripts/e2e_test.py
```

## Estado Atual (Junho 2026)
- Branch: `master`
- MVP completo com busca, RPA judicial, agregação de notícias, dashboard BI
- Deploy: Railway (Docker) / Vercel (serverless)
- Próximos passos: Exportação PDF/CSV, alertas, expansão TRF, grafo de relacionamentos

## Issues Conhecidas / Tech Debt

1. **Pydantic V2 deprecations** (`backend/app/core/config.py`):
   - `@validator` → migrar para `@field_validator`
   - `class Config` → migrar para `ConfigDict`
2. **SQLAlchemy 2.0** (`backend/app/db/base_class.py`):
   - `as_declarative()` → usar `sqlalchemy.orm.as_declarative()`
3. **datetime.utcnow() obsoleto** → usar `datetime.now(datetime.UTC)` (afeta testes e models)
4. **Python 3.14**: projeto usa futures-type hints sem `from __future__ import annotations`
5. **Docker PostgreSQL**: Para testes locais com PostgreSQL, execute `docker compose up` na raiz

## Arquivos Mantidos

### Banco de Dados
- `backend/reveal.db` (3.4 MB) — contém dados reais de processos e notícias. NÃO deletar.

### Scripts de Dados (mantidos)
- `scripts/` — 13 scripts de coleta/população/manutenção
- `backend/scripts/` — 3 scripts utilitários
- Todos são parte ativa do pipeline de dados
