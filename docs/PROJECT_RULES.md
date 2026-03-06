# Memória de Regras e Desenvolvimento - Projeto Reveal

## 1. Arquitetura do Sistema
- **Frontend**: HTML/JS puro com CSS customizado. Focado em simplicidade e performance.
- **Backend**: Python com FastAPI.
- **Banco de Dados**: Supabase (PostgreSQL) para persistência de catálogo e metadados.
- **Resultados Transitórios**: Armazenados em memória durante a sessão de busca, descartados após uso, exceto quando salvos no catálogo.

## 2. Regras de Negócio
- **Consulta Assistida**: O sistema auxilia na busca de informações públicas, sem realizar login ou quebra de captcha complexo.
- **Privacidade**: Dados sensíveis são tratados com cuidado. O catálogo serve para histórico e análise, não para exposição pública indevida.
- **Duplicidade**: Rigorosa verificação de duplicidade para evitar poluição visual e de dados.
  - Critérios: URL normalizada, Título exato, Similaridade de título > 85%, Similaridade de título > 60% com snippet idêntico.
- **Filtros**:
  - "Todos": Deve exibir resultados tanto do jurídico quanto de notícias, garantindo visibilidade balanceada.
  - "Judicial": Apenas processos.
  - "Notícias": Apenas mídia.

## 3. Desenvolvimento e Status Atual
- **Deduplicação**: Implementada camada tripla (Frontend visual, Backend filtro, Script de limpeza profunda).
- **Coleta em Massa**: Script `scripts/mass_collection.py` configurado para rodar em background, coletando até 3000 registros com rotação de estados e termos.
- **Interface**:
  - Botão "Catálogo" simplificado.
  - Filtro "Todos" corrigido para exibir mix de conteúdos.
- **Scripts Utilitários**:
  - `clean_supabase_duplicates.py`: Limpeza profunda de duplicatas.
  - `mass_collection.py`: Coleta automatizada.

## 4. Próximos Passos
- Monitorar a coleta em massa.
- Refinar a interface de visualização de detalhes.
- Implementar exportação de relatórios consolidados.
