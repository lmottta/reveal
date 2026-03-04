# Plano de Migração: PostgreSQL Local para Supabase

## 1. Análise do Esquema
O banco de dados atual consiste em três tabelas principais gerenciadas pelo SQLAlchemy:
- `search`: Armazena consultas de busca e metadados.
- `search_result`: Armazena resultados brutos em JSON vinculados às buscas.
- `news`: Armazena itens de notícias processados vinculados às buscas.

O esquema inclui chaves estrangeiras e tipos de dados padrão (Integer, String, DateTime, JSON).

## 2. Design do Esquema no Supabase
Replicaremos o esquema existente no Supabase usando DDL PostgreSQL padrão.
- `search`: `id` (SERIAL PRIMARY KEY), `query`, `tribunal`, `created_at` (TIMESTAMPTZ DEFAULT NOW()).
- `search_result`: `id`, `search_id` (FK), `content` (JSONB), `created_at`.
- `news`: `id`, `search_id` (FK), `title`, `url`, `source`, `snippet`, `image_url`, `published_date`, `city`, `state`, `created_at`.

### Configuração de Segurança
- **RLS (Row Level Security)**: Habilitar segurança em nível de linha em todas as tabelas.
- **Acesso de Leitura**: Criar uma política `Permitir Leitura Pública` para operações `SELECT` usando `true` para todos os usuários (anon).
- **Acesso de Escrita**: Restringir `INSERT`, `UPDATE`, `DELETE` para usuários autenticados com papéis específicos ou apenas `service_role`. Sem acesso público de escrita.

## 3. Procedimento de Migração

### 3.1. Migração de Esquema
1.  Gerar arquivo de migração SQL `supabase/migrations/001_initial_schema.sql`.
2.  Aplicar migração usando `supabase_apply_migration`.

### 3.2. Migração de Dados
1.  Desenvolver um script Python `backend/migrate_to_supabase.py`.
2.  Conectar ao banco de dados local usando o engine SQLAlchemy existente.
3.  Conectar ao Supabase usando a API REST (`requests`) com a chave `service_role` para inserir dados, contornando a necessidade de senha do banco neste momento.
4.  Ler todos os registros das tabelas locais (`search`, `search_result`, `news`).
5.  Inserir registros no Supabase na ordem de dependência (Search -> SearchResult, News).
6.  Tratar potenciais conflitos (ex: sequências de ID).

### 3.3. Configuração da Aplicação
1.  Atualizar o arquivo `.env` com `SUPABASE_URL` e `SUPABASE_KEY` (Service Role para backend).
2.  Solicitar ao usuário a senha do banco de dados do Supabase para configurar a conexão direta via SQLAlchemy (`SQLALCHEMY_DATABASE_URI`).

### 3.4. Implementação de Segurança
1.  Implementar middleware de autenticação no FastAPI para validar tokens JWT do Supabase.
2.  Proteger endpoints de escrita (ex: POST /search) com este middleware.
3.  Garantir que endpoints de leitura permaneçam públicos conforme solicitado.

## 4. Testes e Verificação
1.  **Verificação de Esquema**: Verificar tabelas e colunas no Supabase.
2.  **Integridade de Dados**: Comparar contagens de registros entre local e Supabase.
3.  **Funcionalidade**: Executar testes existentes `tests/test_e2e.py` contra o novo banco de dados.
4.  **Performance**: Medir latência de consultas.

## 5. Estratégia de Rollback
1.  Reverter `.env` para apontar para o banco de dados local.
2.  O banco de dados local permanece intocado durante a migração, servindo como backup imediato.

## 6. Monitoramento
1.  Usar o Dashboard do Supabase para monitoramento em tempo real.
2.  Configurar alertas para taxas de erro elevadas ou latência.
