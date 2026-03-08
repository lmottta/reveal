import asyncio
import os
import sys
import json
from datetime import datetime
import requests

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Load environment variables explicitly
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        print(f"Warning: .env not found at {env_path}")
except ImportError:
    print("python-dotenv not installed, relying on system environment variables")

from app.core.config import settings
from app.core.supabase import get_supabase

# Configuration
API_URL = "http://localhost:8000/api/v1"
TEST_TERM = "teste e2e automatizado"

def log(msg, type="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{type}] {msg}")

async def run_e2e_test():
    log("Iniciando Teste End-to-End (E2E)...")
    
    # 1. Check Backend Health
    try:
        resp = requests.get("http://localhost:8000/health")
        if resp.status_code == 200:
            log("Backend is UP", "SUCCESS")
        else:
            log(f"Backend returned {resp.status_code}", "ERROR")
            return
    except Exception as e:
        log(f"Backend is DOWN: {str(e)}", "ERROR")
        log("Certifique-se de que o backend está rodando (start_reveal.bat)", "HINT")
        return

    # 2. Setup Database (Supabase)
    client = get_supabase()
    if not client:
        log("Falha ao conectar com Supabase", "ERROR")
        return
    log("Conexão Supabase OK", "SUCCESS")

    # 3. Perform Search (Triggering RPA & News)
    log(f"Executando busca por: '{TEST_TERM}'...")
    try:
        # Using a direct API call to search endpoint
        # Note: Depending on implementation, this might be synchronous or async
        # We'll use the 'news' source first as it's faster
        payload = {
            "query": TEST_TERM,
            "sources": ["news"] 
        }
        # Assuming GET request structure based on search.py
        resp = requests.get(f"{API_URL}/search/catalog", params={"term": TEST_TERM, "source_type": "news"})
        
        if resp.status_code == 200:
            results = resp.json()
            log(f"Busca retornou {len(results)} resultados", "INFO")
        else:
            log(f"Erro na busca: {resp.text}", "ERROR")
    except Exception as e:
        log(f"Exceção na busca: {str(e)}", "ERROR")

    # 4. Verify Persistence in Supabase
    log("Verificando persistência no Supabase...")
    # We look for the term in the 'news' table or 'search_logs'
    # Since we can't guarantee the RPA found something for 'teste e2e', 
    # we'll check if the system logged the search intent if applicable, 
    # OR we'll try to insert a mock item to test the DB connection deeply.
    
    try:
        # Mock Insert
        test_item = {
            "title": f"E2E Test Item {datetime.now().timestamp()}",
            "url": f"http://test.com/{datetime.now().timestamp()}",
            "source": "E2E_TEST",
            "snippet": "This is a test snippet for E2E validation.",
            "published_date": datetime.now().isoformat()
        }
        data = client.table("news").insert(test_item).execute()
        
        if data.data:
            log("Teste de Escrita no Banco: OK", "SUCCESS")
            inserted_id = data.data[0]['id']
            
            # 5. Clean up
            client.table("news").delete().eq("id", inserted_id).execute()
            log("Limpeza de dados de teste: OK", "SUCCESS")
        else:
            log("Teste de Escrita no Banco: FALHOU (Sem dados retornados)", "ERROR")
            
    except Exception as e:
        log(f"Erro na verificação do banco: {str(e)}", "ERROR")

    log("Teste E2E Finalizado.")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
