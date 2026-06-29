import asyncio
import os
import sys
import json
from datetime import datetime
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.search import News

API_URL = "http://localhost:8000/api/v1"
TEST_TERM = "teste e2e automatizado"

def log(msg, type="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{type}] {msg}")

async def run_e2e_test():
    log("Iniciando Teste End-to-End (E2E)...")

    try:
        resp = requests.get("http://localhost:8000/health")
        if resp.status_code == 200:
            log("Backend is UP", "SUCCESS")
        else:
            log(f"Backend returned {resp.status_code}", "ERROR")
            return
    except Exception as e:
        log(f"Backend is DOWN: {str(e)}", "ERROR")
        log("Certifique-se de que o backend está rodando", "HINT")
        return

    log("Testando banco de dados...")
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT 1"))
        log(f"Conexão com banco: OK", "SUCCESS")
    except Exception as e:
        log(f"Falha na conexão: {str(e)}", "ERROR")
        db.close()
        return

    try:
        test_item = News(
            title=f"E2E Test Item {datetime.now().timestamp()}",
            url=f"http://test.com/{datetime.now().timestamp()}",
            source="E2E_TEST",
            snippet="This is a test snippet for E2E validation.",
            published_date=datetime.now().isoformat()
        )
        db.add(test_item)
        db.commit()
        log("Teste de Escrita no Banco: OK", "SUCCESS")
        db.delete(test_item)
        db.commit()
        log("Limpeza de dados de teste: OK", "SUCCESS")
    except Exception as e:
        log(f"Erro na verificação do banco: {str(e)}", "ERROR")
    finally:
        db.close()

    log("Buscando via API...")
    try:
        resp = requests.get(f"{API_URL}/search", params={"q": "estupro"})
        if resp.status_code == 200:
            log(f"API Search OK: {len(resp.json())} resultados", "SUCCESS")
        else:
            log(f"API Search: {resp.status_code}", "WARN")
    except Exception as e:
        log(f"API Search error: {str(e)}", "WARN")

    log("Teste E2E Finalizado.")

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
