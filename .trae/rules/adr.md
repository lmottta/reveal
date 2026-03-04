# ADR-001 — Arquitetura de Consulta Assistida a Processos Judiciais Públicos

## Status
Proposto

## Contexto
Existe a necessidade institucional de realizar **consultas pontuais e assistidas** a processos judiciais públicos,
especialmente para fins de **compliance, proteção de vulneráveis e verificação institucional**.


## Decisão
Adotar uma arquitetura de **Consulta Assistida Transitória**, composta por:

- Interface Web controlada
- Backend Python com orquestração
- Módulos de consulta isolados por tribunal
- Execução RPA sob demanda
- **Banco de Dados PostgreSQL Local (Docker)** para metadados e catálogo (dados sensíveis com retenção controlada)
- Resultados em memória (RAM) para processamento imediato

## Restrições Operacionais
- Alterações devem ocorrer apenas nas entidades solicitadas pelo usuário
- Repopulação de processos não pode apagar ou alterar notícias
- Scripts de seed devem preservar dados fora do escopo solicitado

## Consequências Positivas
- Identificação sumária de processos judiciais
- Uso e coleta indiscriminado dos dados
- Auditoria rastreabilidade técnica
- Arquitetura modular e extensível
- Permitir histórico de consultas
- Permitir análise longitudinal por pessoa
- Persistência estruturada para catálogo local

## Alternativas Consideradas
1. Banco unificado persistente
2. Scraping massivo
3. Consulta manual exclusivamente humana → (Possibilidade de criação de catálogo disponível)
4. Acesso direto a bases oficiais → Dependente de convênio
