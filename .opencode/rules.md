# Rules — Reveal (JuriPopular)

## Engineering Loop

Toda funcionalidade deve seguir o ciclo **Plan → Create → Execute → Test → Review**:

```
┌─────────────────────────────────────────────────┐
│                  ENGINEERING LOOP                │
│   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   │
│   │PLAN  │ → │CREATE│ → │EXECUTE│ → │TEST  │   │
│   └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘   │
│      └──────────↕──────────↕──────────┘        │
│                     REVIEW                      │
│                   (iterar/se necessário)         │
└─────────────────────────────────────────────────┘
```

### 1. PLAN
- Ler `context.md`, `specs.md` para entender o projeto
- Verificar se já existe funcionalidade similar (evitar duplicação)
- Definir critério de aceite: "como saber que está pronto?"
- Mapear arquivos que serão criados/modificados

### 2. CREATE
- Seguir convenções do projeto (Pydantic, SQLAlchemy, FastAPI)
- Não duplicar código existente (endpoints, modelos, lógica)
- Adicionar testes para novos endpoints/lógicas
- Atualizar specs.md se mudar a API

### 3. EXECUTE
```bash
# Modo Docker (PostgreSQL)
docker compose up --build -d

# Modo dev local (SQLite)
cd backend
$env:DATABASE_URL="sqlite:///reveal.db"
uvicorn main:app --reload --port 8000

# Pipeline individual
cd backend
python ../scripts/populate_lawsuits.py
```

### 4. TEST
```bash
# Rodar testes
cd backend
$env:DATABASE_URL="sqlite:///./test_reveal.db"
python -m pytest tests/ -v

# Testar endpoint manual
curl http://localhost:8000/api/v1/search/TJSP?query=teste&state=SP

# Verificar health
curl http://localhost:8000/health
curl http://localhost:8000/diagnostics
```

### 5. REVIEW
- Testes passando? (16/16 obrigatório)
- Lint/typecheck limpo?
- Tech debt introduzido? (se sim, documentar)
- Performance aceitável?
- Segurança: sem expor dados sensíveis
- Documentação atualizada? (context.md, specs.md se aplicável)

## Code Style

### Python (FastAPI)
- Imports padrão → bibliotecas → locais
- Docstrings só em funções públicas
- Async para I/O, sync para CPU-bound
- Named parameters em SQLAlchemy (`filter(Model.col == value)`)
- Preferir `@field_validator` (Pydantic V2) sobre `@validator`

### SQL
- Upper case keywords (`SELECT`, `FROM`, `JOIN`)
- Nomes snake_case
- Evitar `SELECT *`

### Templates (HTML)
- Atributos HTML sem espaços extras
- Event handlers inline só quando necessário
- Fetch API para AJAX em vez de jQuery

## Git
- Commits curtos e descritivos no padrão do repositório
- Não commitar secrets, arquivos temporários, cache, node_modules
- Não commitar sem revisão do diff

## Segurança
- Nunca logar ou expor DATABASE_URL, API keys, tokens
- Validar inputs em endpoints (`Query(...)`, `Path(...)`)
- Headers CSP em todo HTML servido
- LGPD: dados judiciais são BI anônimo
