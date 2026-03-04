from app.db.session import SessionLocal
from app.models.search import Search, SearchResult
import json
import random
from datetime import datetime, timedelta

db = SessionLocal()

print("--- SEEDING MOCK JUDICIAL DATA ---")

# Listas de Nomes para Geração de "Nomes Reais"
NOMES_MASCULINOS = ["Carlos", "Eduardo", "Roberto", "Marcelo", "Felipe", "Gustavo", "Rafael", "Rodrigo", "Bruno", "Lucas", "Gabriel", "Paulo", "Fernando", "Luiz", "Marcos", "André", "Daniel", "Thiago", "Leonardo", "João"]
NOMES_FEMININOS = ["Fernanda", "Patricia", "Camila", "Juliana", "Aline", "Bruna", "Larissa", "Mariana", "Vanessa", "Letícia", "Gabriela", "Beatriz", "Ana", "Maria", "Cristina", "Renata", "Carla", "Priscila", "Amanda", "Jessica"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha", "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques", "Machado", "Mendes", "Freitas"]

def gerar_nome_completo():
    genero = random.choice(["M", "F"])
    if genero == "M":
        nome = random.choice(NOMES_MASCULINOS)
    else:
        nome = random.choice(NOMES_FEMININOS)
    
    sobrenome1 = random.choice(SOBRENOMES)
    sobrenome2 = random.choice(SOBRENOMES)
    
    while sobrenome1 == sobrenome2:
        sobrenome2 = random.choice(SOBRENOMES)
        
    return f"{nome} {sobrenome1} {sobrenome2}"

# Mock Data Generator
def create_mock_process(tribunal, state, city, term):
    process_number = f"{random.randint(1000000, 9999999)}-{random.randint(10, 99)}.{random.randint(2010, 2024)}.8.{random.randint(10, 26)}.{random.randint(1000, 9999)}"
    
    nome_reu = gerar_nome_completo()
    
    return {
        "tribunal": tribunal,
        "processo": process_number,
        "classe": random.choice(["Ação Penal", "Inquérito Policial", "Procedimento Investigatório"]),
        "assunto": random.choice(["Estupro de Vulnerável", "Abuso Sexual", "Pornografia Infantil", "Tráfico de Pessoas"]),
        "foro": f"Foro de {city}",
        "vara": f"{random.randint(1, 5)}ª Vara Criminal",
        "juiz": "Juiz de Direito Substituto",
        "distribuicao": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%d/%m/%Y"),
        "partes": [
            {"tipo": "Autor", "nome": "Ministério Público do Estado"},
            {"tipo": "Réu", "nome": nome_reu},
            {"tipo": "Vítima", "nome": "Sigiloso"}
        ],
        "movimentacoes": [
            {"data": "01/03/2026", "descricao": "Conclusos para Decisão"},
            {"data": "25/02/2026", "descricao": "Juntada de Petição"}
        ],
        "city": city,
        "state": state,
        "source": tribunal
    }

# Tribunals and Locations
locations = [
    {"tribunal": "TJRJ", "state": "RJ", "city": "RIO DE JANEIRO"},
    {"tribunal": "TJRJ", "state": "RJ", "city": "NITEROI"},
    {"tribunal": "TJRJ", "state": "RJ", "city": "DUQUE DE CAXIAS"},
    {"tribunal": "TJSP", "state": "SP", "city": "CAMPINAS"},
    {"tribunal": "TJSP", "state": "SP", "city": "RIBEIRAO PRETO"},
    {"tribunal": "TJMG", "state": "MG", "city": "BELO HORIZONTE"},
    {"tribunal": "TJMG", "state": "MG", "city": "UBERLANDIA"},
    {"tribunal": "TJRS", "state": "RS", "city": "PORTO ALEGRE"},
    {"tribunal": "TJBA", "state": "BA", "city": "SALVADOR"},
    {"tribunal": "TJPE", "state": "PE", "city": "RECIFE"},
]

search_terms = ["estupro vulnerável", "abuso sexual infantil", "pedofilia rede social"]

for loc in locations:
    term = random.choice(search_terms)
    
    # Create Search Record
    search = Search(
        query=f"{term} {loc['city']}",
        tribunal=loc['tribunal'] # Critical for Stats mapping
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    
    # Create Results
    results_list = []
    for _ in range(random.randint(3, 8)):
        results_list.append(create_mock_process(loc['tribunal'], loc['state'], loc['city'], term))
        
    search_result = SearchResult(
        search_id=search.id,
        content={"results": results_list, "status": "success", "tribunal": loc['tribunal']}
    )
    db.add(search_result)
    print(f"Added {len(results_list)} processes for {loc['tribunal']} in {loc['city']}/{loc['state']}")

db.commit()
db.close()
print("--- SEED COMPLETE ---")
