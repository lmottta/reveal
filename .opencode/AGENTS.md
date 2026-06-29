# Agentes OpenCode — Reveal (JuriPopular)

Este arquivo configura agentes especializados para tarefas recorrentes no projeto.

## Agente: Backend Dev

Ativado quando o usuário pede alterações no backend Python/FastAPI.

### Contexto
- Código fonte em `backend/app/`
- FastAPI + SQLAlchemy (PostgreSQL/SQLite) + Playwright
- Database URL configurável via `DATABASE_URL`

### Regras
- Type hints obrigatórios
- Testes em `backend/tests/` ou `scripts/test_system.py`
- Rodar `python -m pytest tests/ -v` antes de finalizar
- Novos RPAs: estender `base.py` ou `systems/base_system.py`; registrar em `rpa/config.py`

---

## Agente: Frontend Dev

Ativado quando o usuário pede alterações na interface HTML/CSS/JS.

### Contexto
- SPA em `backend/static/index.html` (~1872 linhas)
- Leaflet.js para mapas
- Dark theme com CSS variables
- API em `/api/v1/`

### Regras
- JS: ES6+, `const`/`let`, async/await
- CSS: variáveis no `:root`, classes BEM-like
- Manter CSP headers atualizados ao adicionar recursos externos
- Testar visualmente após alterações

---

## Agente: RPA Developer

Ativado quando o usuário pede alterações nos robôs de automação.

### Contexto
- Playwright Python headless
- Sistemas: PJe, e-SAJ, Eproc, Projudi, Tucujuris + custom (TJSP, TJRJ, TJMT)
- CAPTCHA: OCR Tesseract + 2Captcha opcional

### Regras
- Anti-detection obrigatório (User-Agent, viewport, disable automation flags)
- Delays aleatórios entre ações
- Nunca fazer login em portais
- Nunca buscar por CPF
- Tratar erros por tribunal (não derrubar o sistema)

---

## Agente: Data Pipeline

Ativado quando o usuário pede coleta/população de dados ou scripts de manutenção.

### Contexto
- Scripts em `scripts/` e `backend/scripts/`
- Fontes: Google News, DuckDuckGo, RSS de 14 portais, 27 tribunais
- Destino: PostgreSQL (Docker) ou SQLite (`backend/reveal.db`)

### Regras
- Deduplicação em 3 níveis obrigatória (URL → fuzzy → contextual)
- Filtragem por keywords de crimes sexuais
- Validar CNJ antes de inserir
- Respeitar rate limits dos portais
