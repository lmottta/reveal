# Regras de Desenvolvimento — Reveal (JuriPopular)

## 1. Convenções de Código

### Python
- **Versão:** Python 3.10+
- **Formatação:** Seguir PEP 8
- **Imports:** Ordem: standard library → third-party → local (separados por linha em branco)
- **Type hints:** Obrigatórios em funções públicas
- **Docstrings:** Google-style apenas para funções complexas (>15 linhas)
- **Naming:** `snake_case` para funções/variáveis, `PascalCase` para classes, `UPPER_CASE` para constantes
- **Comentários:** Evitar comentários óbvios. Comentar apenas "por quê", não "o quê"
- **Max line length:** 120 caracteres

### Frontend (HTML/CSS/JS)
- **HTML:** Semântico, indentação 2 espaços
- **CSS:** Variáveis CSS no `:root` para theming (dark mode), classes BEM-like
- **JS:** ES6+, `const`/`let` (nunca `var`), async/await para promises
- **Leaflet:** Inicialização via CDN, tiles OpenStreetMap

### Git
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`)
- **Mensagens:** Português ou Inglês (manter consistência). Ex: `feat: adiciona exportação de relatórios`
- **Branch:** `master` principal, features em branches separadas
- **NUNCA** commitar: `.env`, `*.key`, `*.pem`, `venv/`, `__pycache__/`, `debug_*`
- **SEMPRE** verificar `git status` e `git diff` antes de commitar

## 2. Estrutura de Código

### Backend (`backend/app/`)
```
app/
├── api/           # FastAPI routers e endpoints
│   └── endpoints/ # Handlers de cada recurso
├── core/          # Config, constants, utilities
├── db/            # Database session e init
├── middleware/    # Auth e outros middlewares
├── models/        # SQLAlchemy models
└── rpa/           # Robotic Process Automation
    └── systems/   # RPAs por sistema judiciário
```

### Regras para novos endpoints:
1. Criar arquivo em `api/endpoints/` com named router
2. Registrar em `api/api.py`
3. Usar `Session` do SQLAlchemy como dependência (mesma `get_db` dos endpoints existentes)

### Regras para novos RPAs:
1. Estender `rpa/base.py` (RPA interface) ou `rpa/systems/base_system.py` (sistema judiciário)
2. Registrar em `rpa/config.py` (tribunal → RPA)
3. Playwright headless obrigatório com anti-detection

## 3. Qualidade e Testes

- **SEMPRE** rodar testes antes de commitar:
  ```bash
  cd backend && python -m pytest tests/ -v
  ```
- **Novos recursos** devem ter testes correspondentes
- **Testes unitários** em `backend/tests/` (unittest/pytest)
- **Testes de sistema** em `scripts/test_system.py`
- **E2E** em `scripts/e2e_test.py` (requer backend rodando)

## 4. Segurança

- **NUNCA** expor `CAPTCHA_API_KEY` em logs ou responses
- **CSP**: Manter Content-Security-Policy headers atualizados ao adicionar novos recursos (fonts, map tiles, etc.)
- **CORS**: Configurar origins permitidas em `core/config.py`
- **Auth**: Endpoints de escrita protegidos por JWT (ver `middleware/auth.py`)
- **Dados sensíveis**: Nomes de partes/juízes não expostos na UI final

## 5. RPA - Boas Práticas

### Playwright
- Sempre usar `headless=True` em produção
- `user_agent` customizado (evitar `HeadlessChrome`)
- `args=["--disable-blink-features=AutomationControlled"]`
- Injetar script anti-detection: `navigator.webdriver === undefined`
- `locale="pt-BR"` e `timezone="America/Sao_Paulo"`

### Rate Limiting
- Delay aleatório entre ações: `random.uniform(0.5, 2.0)`
- Typping humano simulado: `page.keyboard.type(text, delay=random.randint(50, 150))`
- Timeouts: 15-60s por operação

### Erros
- Tratar timeouts e mudanças de layout individualmente (não derrubar o sistema)
- Log de erros sem expor dados sensíveis
- Screenshots de debug salvos apenas localmente (gitignorados)

## 6. Fluxo de Desenvolvimento

1. **Analisar** o requisito e entender o impacto nos arquivos existentes
2. **Consultar** `.opencode/context.md` e `.opencode/specs.md` para contexto
3. **Seguir** as convenções existentes no código
4. **Implementar** com testes
5. **Verificar** com `pytest` e lint
6. **Commit** com mensagem Conventional Commit

## 7. Arquivos que NUNCA Devem Ser Modificados Manualmente

- `backend/static/vendor/leaflet/` — bibliotecas third-party
- `backend/reveal.db` — dados de produção
- `migrations/init.sql` e `migrations/seed.sql` — scripts de inicialização do PostgreSQL
- `requirements.txt` — apenas via `pip freeze > requirements.txt`

## 8. Performance

- Queries com mais de 500ms devem ser otimizadas (índices SQL, paginação)
- RPA lento é aceitável (latência externa), mas não deve bloquear a API principal
- Usar `async` para operações I/O-bound na API
- Usar `sync` para RPA (Playwright síncrono é mais estável)
