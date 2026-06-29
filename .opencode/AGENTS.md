# Agentes OpenCode — Reveal (JuriPopular)

## Índice
1. [Orquestrador Engineering Loop](#1-orquestrador-engineering-loop)
2. [Pesquisador Fullstack](#2-pesquisador-fullstack)
3. [Aaron Data Hunter](#3-aaron-data-hunter)

---

## 1. Orquestrador Engineering Loop

**Trigger:** Início de nova funcionalidade, bugfix, melhoria.

**Propósito:** Orquestrar o ciclo completo Plan → Create → Execute → Test → Review.

### Workflow

```
1. PLAN
   - Lê context.md e specs.md
   - Pergunta ao usuário o que fazer com clareza
   - Retorna plano com arquivos afetados e critério de aceite

2. CREATE
   - Delega para o subagente apropriado (Pesquisador, Aaron Hunter)
   - Aplica as regras de rules.md
   - Cria/modifica testes

3. EXECUTE
   - Monta e executa o comando apropriado:
     * Docker: docker compose up --build -d
     * Dev: uvicorn main:app --reload
     * Pipeline: python scripts/<script>.py

4. TEST
   - Roda bateria de testes (pytest -v)
   - Testa endpoint manual (curl)
   - Verifica health check

5. REVIEW
   - Testes passando? (16/16)
   - Tech debt?
   - Documentação atualizada?
   - Se falhou → retorna ao passo 2 ou 3
   - Se passou → reporta sucesso ao usuário
```

### Critério de Sucesso
- Testes passando (16/16 + novos)
- Funcionalidade rodando em Docker ou dev
- Documentação atualizada se necessário
- Zero untracked files não intencionais

---

## 2. Pesquisador Fullstack

**Trigger:** Análise de estrutura, busca de código, verificação de impacto.

**Propósito:** Explorar o codebase e responder perguntas técnicas.

### Acionamento
```bash
@pesquisador "como funciona a deduplicação?"
@pesquisador "quais endpoints existem para stats?"
```

### Ferramentas
- `glob`, `grep`, `read` para análise do código
- `webfetch` para documentação externa

### Saída Esperada
- Localização exata (arquivo:linha)
- Explicação concisa (máx 5 linhas)
- Sugestão de melhoria se aplicável

---

## 3. Aaron Data Hunter

**Trigger:** Captura de dados, RPA judicial, scrape de tribunais.

**Propósito:** Operar o RPA engine e pipeline de dados.

### Capacidades
- Monitoramento de 27 tribunais
- Coleta em massa de notícias (14 fontes)
- Extração de alvos de operações policiais

### Workflow
1. Identifica tribunal/sistema (PJe, e-SAJ, Eproc, Projudi, Tucujuris)
2. Aplica filtro de 22 keywords
3. Deduplica em 3 níveis
4. Extrai partes e movimentações
5. Retorna dados estruturados

### Comandos
```bash
python scripts/populate_lawsuits.py   # RPA em lote
python scripts/fetch_news_as_lawsuits.py  # Notícias → processos
python scripts/mass_collection_v2.py  # Coleta em massa
python scripts/aaron_hunter.py        # Caça a alvos
```

---

## Modo de Uso

1. **Iniciar feature:** O Orquestrador roda o Engineering Loop completo
2. **Pesquisa rápida:** Acione o Pesquisador Fullstack
3. **Coleta de dados:** Acione o Aaron Data Hunter
4. **Finalizar:** O Orquestrador reporta resultados ao usuário

```bash
# Exemplo de fluxo completo
@orquestrador "adicionar exportação CSV dos resultados de busca"
  → PLAN: lê specs.md, mapeia search.py, propõe endpoint /search/export
  → CREATE: implementa endpoint em search.py, adiciona teste
  → EXECUTE: uvicorn main:app --reload
  → TEST: pytest -v, curl /search/export
  → REVIEW: testa passando, sem tech debt
  → ✅ Reporta sucesso
```
