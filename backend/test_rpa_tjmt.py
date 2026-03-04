from app.rpa.tjmt import TJMTRPA
import json

def test_search():
    rpa = TJMTRPA()
    
    print("Testing RPA TJMT...")

    # Test 1: ID fornecido pelo usuário
    query_id = "2407408-69.2024.8.11.3117"
    print(f"\n[TEST 1] Buscando ID '{query_id}'...")
    try:
        result = rpa.search(query_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
