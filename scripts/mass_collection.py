import sys
import os
import time
import random
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

# Load environment variables from backend/.env
try:
    from dotenv import load_dotenv
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        print(f"Loading .env from {env_path}")
        load_dotenv(env_path)
    else:
        print(f"Warning: .env not found at {env_path}")
except ImportError:
    print("python-dotenv not installed, relying on system environment variables")

from app.rpa.google_news import GoogleNewsRPA
from app.core.supabase import supabase

RELEVANT_KEYWORDS = [
    "EXPLORACAO SEXUAL",
    "EXPLORACAO SEXUAL INFANTO JUVENIL",
    "ABUSO SEXUAL",
    "ABUSO SEXUAL INFANTIL",
    "ABUSO SEXUAL DE INCAPAZ",
    "ESTUPRO",
    "ESTUPRO DE VULNERAVEL",
    "VIOLENCIA SEXUAL",
    "TRAFICO SEXUAL",
    "TRAFICO DE PESSOAS",
    "PORNOGRAFIA INFANTIL",
    "PEDOFILIA",
    "ALICIAMENTO",
    "ABUSO DE MENOR",
    "ABUSO INFANTIL",
    "CRIME SEXUAL",
    "CRIMES SEXUAIS",
    "PREDADOR SEXUAL",
    "PREDADORES SEXUAIS",
    "EXPLORACAO DE VULNERAVEL",
    "VIOLENCIA SEXUAL CONTRA MULHER",
    "VIOLENCIA SEXUAL CONTRA MULHERES"
]

SEARCH_TERMS = [
    "exploração sexual infanto juvenil",
    "exploração sexual de vulnerável",
    "abuso sexual infantil",
    "abuso sexual de incapaz",
    "estupro de vulnerável",
    "violência sexual contra mulheres",
    "violência sexual contra menores",
    "tráfico sexual",
    "tráfico de pessoas exploração sexual",
    "predador sexual prisão",
    "pornografia infantil operação policial",
    "pedofilia investigação",
    "aliciamento de menores internet crime",
    "crime sexual contra vulneráveis",
    "estupro prisão preventiva",
    "condenação estupro",
    "prisão em flagrante abuso sexual",
    "operação policial abuso menores",
    "rede de pedofilia desmantelada",
    "sentença condenatória estupro"
]

STATES = [
    "SP", "RJ", "MG", "RS", "PR", "SC", "BA", "PE", "CE", "GO",
    "AM", "PA", "MT", "MS", "ES", "DF", "MA", "PB", "RN", "AL",
    "PI", "SE", "RO", "TO", "AC", "AP", "RR"
]

def normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.upper()

def is_relevant_content(value: str) -> bool:
    text = normalize_text(value)
    return any(keyword in text for keyword in RELEVANT_KEYWORDS)

def normalize_url(value):
    if not value:
        return ""
    try:
        parts = urlsplit(value.strip())
        query_items = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "igshid", "mc_cid", "mc_eid"}
        ]
        query = urlencode(query_items, doseq=True)
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc, path, query, "")).lower()
    except Exception:
        return value.strip().lower()

def mass_collection():
    rpa = GoogleNewsRPA()
    total_collected = 0
    target = 3000  # Target number of records
    
    print(f"Starting mass collection. Target: {target} records.")
    
    # Shuffle states and keywords to get variety
    random.shuffle(STATES)
    random.shuffle(SEARCH_TERMS)
    
    for state in STATES:
        for keyword in SEARCH_TERMS:
            if total_collected >= target:
                print("Target reached!")
                return

            query = f"{keyword} {state}"
            print(f"Searching for: {query}...")
            
            try:
                # Search with max_pages=5 (approx 50 results per query)
                result = rpa.search(query, max_pages=5)
                
                if result.get("status") != "success":
                    print(f"Failed to search for {query}: {result.get('error')}")
                    continue
                
                items = result.get("results", [])
                print(f"Found {len(items)} items for {query}")
                
                new_items_count = 0
                for item in items:
                    # Relevance Check
                    text = f"{item.get('title', '')} {item.get('snippet', '')}"
                    if not is_relevant_content(text):
                        continue
                        
                    # Normalize URL
                    url = normalize_url(item.get("url"))
                    
                    # Prepare record
                    record = {
                        "title": item["title"],
                        "url": url,
                        "source": item["source"],
                        "snippet": item["snippet"],
                        "image_url": item.get("image_url"),
                        "published_date": item.get("published_date"),
                        "city": item.get("city") or "DESCONHECIDO",
                        "state": item.get("state") or state, # Use query state if missing
                        "created_at": datetime.now().isoformat(),
                        "search_id": None # System collection
                    }
                    
                    try:
                        # Check URL existence in DB
                        existing = supabase.table("news").select("id").eq("url", url).execute()
                        if existing.data:
                            continue
                        
                        # Check Title existence (Exact)
                        existing_title = supabase.table("news").select("id").eq("title", item["title"]).execute()
                        if existing_title.data:
                            continue
                            
                        supabase.table("news").insert(record).execute()
                        new_items_count += 1
                        total_collected += 1
                    except Exception as e:
                        # Ignore insertion errors
                        # print(f"Error inserting: {e}")
                        pass
                        
                print(f"Saved {new_items_count} new items. Total so far: {total_collected}")
                
                # Sleep to avoid rate limits
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"Error processing {query}: {e}")
                time.sleep(5)

    print(f"Mass collection finished. Total collected: {total_collected}")

if __name__ == "__main__":
    mass_collection()
