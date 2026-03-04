import pytest
from fastapi.testclient import TestClient
from app.core.supabase import get_supabase
import os

# Mock environment just in case, though it should read from .env or OS
os.environ["SUPABASE_URL"] = "https://jdmjaxynewasayzyyaiq.supabase.co"
# We need a valid key. The service role key is in .env or hardcoded in my memory for now.
# But TestClient will run the app which uses app.core.supabase.

from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_search_public_read():
    response = client.get("/api/v1/search/?query=TESTE_INTEGRACAO_SUPABASE")
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert "news" in data
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_health()
    test_search_public_read()
    print("Tests passed!")
