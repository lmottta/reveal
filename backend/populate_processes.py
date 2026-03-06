import sys
import os
import time
import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.search import Search, SearchResult
from app.rpa.tjsp import TJSPRPA
from app.rpa.tjrj import TJRJRPA

# Termos de busca para teste de integração
TERMOS_BUSCA = [
    "Fazenda Publica do Estado de Sao Paulo",
    "Municipio de Sao Paulo"
]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_rpa_for_tribunal(rpa_instance, tribunal_name, query, db: Session):
    print(f"[{tribunal_name}] Buscando: {query}...")
    try:
        result = rpa_instance.search(query)
        
        if result.get("status") == "success":
            results_list = result.get("results", [])
            seen = set()
            unique_results = []
            for item in results_list:
                raw_process = item.get("processo") or item.get("numero_processo") or item.get("id")
                key = str(raw_process or "").strip()
                if not key:
                    key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                unique_results.append(item)
            results_list = unique_results
            print(f"[{tribunal_name}] Encontrados {len(results_list)} processos.")
            
            if results_list:
                # Criar registro de busca pai
                search_record = Search(
                    query=query,
                    tribunal=tribunal_name
                )
                db.add(search_record)
                db.commit()
                db.refresh(search_record)
                
                # Salvar cada resultado como JSON
                for item in results_list:
                    # Garantir que o item seja serializável em JSON
                    search_result = SearchResult(
                        search_id=search_record.id,
                        content=item
                    )
                    db.add(search_result)
                
                db.commit()
                print(f"[{tribunal_name}] Resultados salvos no banco.")
            else:
                 print(f"[{tribunal_name}] Nenhum processo encontrado para '{query}'.")

        elif result.get("status") == "error":
             print(f"[{tribunal_name}] Erro na execução: {result.get('error')}")
        else:
            print(f"[{tribunal_name}] Retorno inesperado: {result}")
            
    except Exception as e:
        print(f"[{tribunal_name}] Falha crítica: {e}")

def main():
    print("Iniciando coleta de processos judiciais...")
    print("NOTA: Certifique-se de que o banco de dados está rodando e acessível.")
    
    db = next(get_db())
    
    # Lista de RPAs a executar
    # Adicione novos tribunais aqui conforme forem implementados
    rpas = [
        (TJSPRPA(), "TJSP"),
        (TJRJRPA(), "TJRJ")
    ]
    
    for query in TERMOS_BUSCA:
        for rpa, name in rpas:
            run_rpa_for_tribunal(rpa, name, query, db)
            # Pausa para evitar bloqueio agressivo
            time.sleep(5) 

if __name__ == "__main__":
    main()
