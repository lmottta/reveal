# Documentação de RPA e Coleta de Processos

Este módulo é responsável pela coleta automatizada de dados processuais em tribunais públicos (TJSP, TJRJ, etc.) e consolidação na base de dados.

## Estrutura

- `backend/app/rpa/base.py`: Classe base abstrata para todos os RPAs.
- `backend/app/rpa/tjsp.py`: Implementação para o Tribunal de Justiça de São Paulo.
- `backend/app/rpa/tjrj.py`: Implementação para o Tribunal de Justiça do Rio de Janeiro.
- `backend/populate_processes.py`: Script orquestrador para execução em lote.

## Como Executar

Certifique-se de estar no diretório `backend` e com o ambiente virtual ativado.

```bash
./venv/Scripts/python populate_processes.py
```

## Adicionando Novos Tribunais

1. Crie um novo arquivo em `backend/app/rpa/` (ex: `tjmg.py`).
2. Herde de `BaseRPA` e implemente o método `search(query)`.
3. Adicione a nova classe na lista `rpas` dentro de `populate_processes.py`.

## Dados Coletados

Os resultados são salvos na tabela `search_results` do banco de dados PostgreSQL, vinculados a um registro mestre na tabela `search`.

## Notas de Implementação

- Os scripts utilizam Playwright em modo headless.
- É necessário manter os seletores CSS atualizados conforme mudanças nos portais dos tribunais.
- Respeite os rate limits e termos de uso de cada tribunal.
