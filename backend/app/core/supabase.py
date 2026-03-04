import os
import sys
from app.core.config import settings

# Try importing standard supabase client
try:
    from supabase import create_client, Client
    USE_LITE = False
except ImportError:
    # Fallback if supabase fails (e.g. pyiceberg missing)
    USE_LITE = True

# Always try to import postgrest as fallback backend
try:
    from postgrest import SyncPostgrestClient
except ImportError:
    SyncPostgrestClient = None

class SupabaseLiteClient:
    def __init__(self, url: str, key: str):
        if not SyncPostgrestClient:
            raise ImportError("postgrest library not found")
            
        self.rest_url = f"{url}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        # Postgrest client initialization
        self.client = SyncPostgrestClient(self.rest_url, headers=self.headers, schema="public")

    def table(self, table_name: str):
        return self.client.from_(table_name)

    def rpc(self, func_name: str, params: dict):
        return self.client.rpc(func_name, params)

SUPABASE_URL = settings.SUPABASE_URL or os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = None

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print(f"Warning: SUPABASE_URL or KEY not set. URL: {SUPABASE_URL}, KEY_LEN: {len(str(SUPABASE_SERVICE_KEY)) if SUPABASE_SERVICE_KEY else 0}")
else:
    # Attempt 1: Standard Client
    if not USE_LITE:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("Standard Supabase Client initialized successfully.")
        except Exception as e:
            print(f"Standard Supabase Client failed: {e}")
            USE_LITE = True # Fallback to Lite
    
    # Attempt 2: Lite Client
    if USE_LITE or not supabase:
        try:
            print("Initializing Supabase Lite Client...")
            supabase = SupabaseLiteClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("Supabase Lite Client initialized successfully.")
        except Exception as e:
            print(f"Supabase Lite Client failed: {e}")
            supabase = None

def get_supabase():
    return supabase
