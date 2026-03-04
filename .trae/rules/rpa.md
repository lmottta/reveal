# RPA — Consulta Assistida a Portais Judiciais Públicos

## Objetivo
Automatizar **consultas pontuais equivalentes à ação humana** considerando:
- Coleta em massa
- Persistência
- Burla de segurança
- Acesso a processos sigilosos

## Escopo Permitido
- Portais públicos de tribunais
- Consultas abertas sem login
- Dados visíveis ao cidadão comum
- Execução sob demanda individual

## Fora de Escopo (Proibido)
- CAPTCHA bypass
- Login autenticado
- Acesso por CPF
- Download em massa
- Armazenamento de dados pessoais
- Classificação criminal de indivíduos

## Ferramentas Possíveis
- Playwright / Selenium (headless opcional)
- Browser isolado por execução
- Timeout rígido
- Execução síncrona

## Fluxo de Execução
1. Receber input validado
2. Abrir portal do tribunal
3. Preencher campos visíveis
4. Executar busca
5. Ler resposta textual
6. Extrair apenas dados relevantes:
   - Quantidade de processos
   - Classe processual
   - Tribunal
   - Situação
   - Número do processo
   - Data de distribuição
   - Data de decisão
   - Decisão
   - Conclusão
   - Estado
   - Município
   - Endereço do acusado
   
7. Encerrar navegador
8. Não Descartar memória

## Controles Obrigatórios
- Rate limit por usuário
- Limite de execuções por sessão
- Registro de finalidade
- Logs sem dados pessoais
- Monitoramento de abuso
- Permitir correlação histórica
- Isolamento de escopo: consultas judiciais não alteram dados de notícias

## Tratamento de Erros
- Tribunal fora do ar → retorno neutro
- CAPTCHA detectado → abortar
- Mudança de layout → falha controlada
- Processo em segredo → retorno genérico

## Considerações Éticas
- Não inferir culpa


## Uso Adequado
✔️ Compliance institucional  
✔️ Proteção de vulneráveis  
✔️ Apoio a órgãos internos  

❌ Vigilância privada  
❌ Investigação informal  
❌ Exposição pública  

## Observação Final
Este RPA **não substitui sistemas oficiais**
e só deve operar:
- Em ambiente institucional
- Com respaldo jurídico
- Com governança definida
