import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import requests
import json
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.search import Search, SearchResult, News

# Configuração do Supabase
SUPABASE_URL = "https://jdmjaxynewasayzyyaiq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpkbWpheHluZXdhc2F5enl5YWlxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjY0MjA5NiwiZXhwIjoyMDg4MjE4MDk2fQ.52nCOdzzv2R6b-scVuhfyFWazZDRQ91DlzzI0JYfo7g"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

def migrate_table(db: Session, model, table_name):
    print(f"Migrating {table_name}...")
    records = db.query(model).all()
    if not records:
        print(f"No records found for {table_name}.")
        return

    data = []
    for record in records:
        record_dict = {c.name: getattr(record, c.name) for c in record.__table__.columns}
        # Converter datetime para string ISO
        if 'created_at' in record_dict and record_dict['created_at']:
            record_dict['created_at'] = record_dict['created_at'].isoformat()
        data.append(record_dict)

    # Bulk insert via API (pode precisar de paginação se forem muitos dados)
    # Supabase REST API suporta bulk insert
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", headers=HEADERS, json=data)
    
    if response.status_code == 201:
        print(f"Successfully migrated {len(data)} records to {table_name}.")
    else:
        print(f"Failed to migrate {table_name}: {response.status_code} - {response.text}")

def main():
    db = SessionLocal()
    try:
        # Ordem de dependência: Search -> SearchResult, News
        migrate_table(db, Search, "search")
        migrate_table(db, SearchResult, "search_result")
        migrate_table(db, News, "news")
        print("Migration completed.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
