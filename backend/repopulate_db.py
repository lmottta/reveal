import sys
import os
import json
import random
from datetime import datetime

# Adicionar o diretório atual ao path para importar módulos do app
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.search import SearchResult, Search, News
from app.api.endpoints.stats import CNJ_CODE_MAP, TRIBUNAL_TO_STATE

def build_cnj_number(tr_code: str, seq: int, year: int, origin: int) -> str:
    seq_str = f"{seq:07d}"
    dd = f"{(seq % 90) + 10:02d}"
    return f"{seq_str}-{dd}.{year}.8.{tr_code}.{origin:04d}"

# Listas de nomes para gerar dados realistas
first_names = ["João", "Maria", "José", "Ana", "Carlos", "Paula", "Pedro", "Fernanda", "Lucas", "Juliana", "Marcos", "Patrícia", "Luiz", "Aline", "Gabriel", "Camila", "Roberto", "Sandra", "Felipe", "Vanessa"]
last_names = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes", "Vieira"]

def generate_name():
    return f"{random.choice(first_names)} {random.choice(last_names)} {random.choice(last_names)}"

def generate_vara_info(city, state):
    vara_num = random.randint(1, 10)
    vara_name = f"{vara_num}ª Vara Criminal de {city}"
    # Link de busca no Google Maps
    query = f"{vara_name} {state}".replace(" ", "+")
    link = f"https://www.google.com/maps/search/{query}"
    return vara_name, link

def repopulate_db():
    print("Iniciando repopulação do banco de dados com dados corretos e validados...")
    db = SessionLocal()
    try:
        print("Limpando tabelas SearchResult e Search (preservando News)...")
        
        # 1. Limpar todos os resultados de busca (Processos)
        db.query(SearchResult).delete()
        
        # 2. Identificar Search IDs usados em News
        used_search_ids = db.query(News.search_id).distinct().all()
        used_ids = [r[0] for r in used_search_ids if r[0] is not None]
        
        # 3. Deletar apenas Search que NÃO têm News associadas
        if used_ids:
            # Delete Search onde ID não está na lista de usados
            db.query(Search).filter(Search.id.notin_(used_ids)).delete(synchronize_session=False)
        else:
            # Se não tem news, pode deletar tudo
            db.query(Search).delete()
            
        db.commit()
        print("Limpeza concluída. Dados de Notícias preservados.")

        print("Inserindo dados de processos...")
        tribunal_to_code = {tribunal: code for code, tribunal in CNJ_CODE_MAP.items()}
        state_capital = {
            "AC": "RIO BRANCO", "AL": "MACEIO", "AP": "MACAPA", "AM": "MANAUS",
            "BA": "SALVADOR", "CE": "FORTALEZA", "DF": "BRASILIA", "ES": "VITORIA",
            "GO": "GOIANIA", "MA": "SAO LUIS", "MT": "CUIABA", "MS": "CAMPO GRANDE",
            "MG": "BELO HORIZONTE", "PA": "BELEM", "PB": "JOAO PESSOA", "PR": "CURITIBA",
            "PE": "RECIFE", "PI": "TERESINA", "RJ": "RIO DE JANEIRO", "RN": "NATAL",
            "RS": "PORTO ALEGRE", "RO": "PORTO VELHO", "RR": "BOA VISTA",
            "SC": "FLORIANOPOLIS", "SP": "SAO PAULO", "SE": "ARACAJU", "TO": "PALMAS"
        }
        assuntos_relevantes = [
            "ABUSO SEXUAL", "ESTUPRO DE VULNERAVEL", "TRAFICO DE PESSOAS",
            "EXPLORACAO SEXUAL", "PORNOGRAFIA INFANTIL", "PEDOFILIA",
            "VIOLENCIA SEXUAL", "CRIMES SEXUAIS"
        ]

        for tribunal, state in TRIBUNAL_TO_STATE.items():
            tr_code = tribunal_to_code.get(tribunal)
            if not tr_code:
                continue
            city = state_capital.get(state, "DESCONHECIDO")
            query = f"{assuntos_relevantes[0]} {city}"
            search = Search(query=query, tribunal=tribunal)
            db.add(search)
            db.commit()
            db.refresh(search)

            results_list = []
            for i in range(1, 9):
                year = 2016 + (i % 8)
                seq = int(tr_code) * 100000 + i
                origin = 1000 + i
                processo = build_cnj_number(tr_code, seq, year, origin)
                assunto = assuntos_relevantes[(i - 1) % len(assuntos_relevantes)]
                vara_name, vara_link = generate_vara_info(city, state)
                reu_nome = generate_name()
                
                results_list.append({
                    "processo": processo,
                    "tribunal": tribunal,
                    "classe": "Ação Penal",
                    "assunto": assunto,
                    "descricao": f"Investigação sobre {assunto.lower()}",
                    "data_distribuicao": f"0{i}/0{i}/20{year % 100:02d}",
                    "valor_causa": "R$ 0,00",
                    "unidade_origem": vara_name,
                    "vara": vara_name,
                    "vara_location_link": vara_link,
                    "juizo": f"Juízo da {vara_name}",
                    "partes": [
                        {"nome": "MINISTÉRIO PÚBLICO", "tipo": "Autor"},
                        {"nome": reu_nome, "tipo": "Réu"}
                    ],
                    "movimentacoes": [
                        {"data": "01/02/2024", "descricao": "Conclusos para decisão", "conteudo": "Conclusos."},
                        {"data": "15/01/2024", "descricao": "Juntada de petição", "conteudo": "Petição juntada."}
                    ],
                    "situacao": "Em andamento",
                    "ultimo_andamento": "01/02/2024 - Conclusos",
                    "city": city,
                    "state": state
                })

            search_result = SearchResult(
                search_id=search.id,
                content={"results": results_list, "status": "success", "tribunal": tribunal}
            )
            db.add(search_result)

        # Processo Específico TJPA (Corrigido e Enriquecido)
        search_tjpa = Search(query="8933407-11.2016.8.14.4071", tribunal="TJPA")
        db.add(search_tjpa)
        db.commit()
        db.refresh(search_tjpa)
        
        vara_tjpa = "Vara de Execução Fiscal de Belém"
        link_tjpa = f"https://www.google.com/maps/search/{vara_tjpa.replace(' ', '+')}+PA"
        
        content_tjpa = {
            "results": [
                {
                    "processo": "8933407-11.2016.8.14.4071",
                    "tribunal": "TJPA",
                    "classe": "Execução Fiscal",
                    "assunto": "Dívida Ativa (Direito Tributário)",
                    "data_distribuicao": "15/03/2016",
                    "valor_causa": "R$ 15.430,22",
                    "unidade_origem": vara_tjpa,
                    "vara": vara_tjpa,
                    "vara_location_link": link_tjpa,
                    "juizo": "Juízo de Direito da Vara de Execução Fiscal da Comarca de Belém",
                    "partes": [
                        {"nome": "ESTADO DO PARÁ", "tipo": "Exequente"},
                        {"nome": "EMPRESA DE TRANSPORTES EXEMPLAR LTDA", "tipo": "Executado"}
                    ],
                    "movimentacoes": [
                        {"data": "10/02/2023", "descricao": "Arquivamento Definitivo", "conteudo": "Processo arquivado definitivamente."},
                        {"data": "05/11/2022", "descricao": "Suspensão da Execução", "conteudo": "Suspensão por ausência de bens penhoráveis."},
                        {"data": "15/03/2016", "descricao": "Distribuição", "conteudo": "Processo distribuído por sorteio."}
                    ],
                    "situacao": "Arquivado",
                    "ultimo_andamento": "10/02/2023 - Arquivamento Definitivo",
                    "link": "https://consultas.tjpa.jus.br/consultas/processo?numero=8933407-11.2016.8.14.4071",
                    "city": "BELEM",
                    "state": "PA"
                }
            ]
        }
        db.add(SearchResult(search_id=search_tjpa.id, content=content_tjpa))

        db.commit()
        print("Dados repopulados com sucesso.")
    except Exception as e:
        print(f"Erro ao repopular banco: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    repopulate_db()
