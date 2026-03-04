from app.rpa.tjsp import TJSPRPA
import json

def test_search():
    rpa = TJSPRPA()
    
    print("Testing RPA TJSP...")

    # Test 1: Nome Comum (Espera-se 'Muitos processos' ou lista)
    query_nome = "SILVA"
    print(f"\n[TEST 1] Buscando Nome '{query_nome}'...")
    try:
        result = rpa.search(query_nome)
        print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: ID Inválido/Inexistente (Espera-se 'Não encontrado')
    query_id = "1000001-06.2024.8.26.0001"
    print(f"\n[TEST 2] Buscando ID '{query_id}'...")
    try:
        result = rpa.search(query_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
