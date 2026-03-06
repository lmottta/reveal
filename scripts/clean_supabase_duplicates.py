import sys
import os
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Add backend directory to sys.path to allow imports
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

from app.core.supabase import supabase

def normalize_text(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    return text.lower().strip()

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

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def clean_duplicates():
    print("Fetching news from Supabase...")
    all_news = []
    page = 0
    page_size = 1000
    
    while True:
        print(f"Fetching page {page}...")
        response = supabase.table("news").select("*").range(page * page_size, (page + 1) * page_size - 1).execute()
        data = response.data
        if not data:
            break
        all_news.extend(data)
        if len(data) < page_size:
            break
        page += 1
        
    print(f"Total records fetched: {len(all_news)}")
    
    ids_to_delete = set()
    
    # 1. Exact Normalized URL Duplicates
    print("Analyzing Normalized URL duplicates...")
    url_groups = defaultdict(list)
    for item in all_news:
        u = normalize_url(item.get("url", ""))
        if u: url_groups[u].append(item)
            
    for u, items in url_groups.items():
        if len(items) > 1:
            # Keep the oldest one (first created)
            items.sort(key=lambda x: x.get("created_at") or "")
            kept = items[0]
            for duplicate in items[1:]:
                ids_to_delete.add(duplicate["id"])
                # print(f"[URL] Deleting: {duplicate.get('url')} (ID: {duplicate['id']})")

    # 2. Fuzzy Title Duplicates
    print("Analyzing Fuzzy Title duplicates...")
    # Filter out already deleted items
    remaining_items = [i for i in all_news if i["id"] not in ids_to_delete]
    # Sort by date (keep oldest)
    remaining_items.sort(key=lambda x: x.get("created_at") or "")
    
    kept_items = []
    
    for item in remaining_items:
        current_title = normalize_text(item.get("title", ""))
        current_snippet = normalize_text(item.get("snippet", ""))
        
        if not current_title:
            continue
            
        is_dup = False
        for kept in kept_items:
            kept_title = normalize_text(kept.get("title", ""))
            kept_snippet = normalize_text(kept.get("snippet", ""))
            
            # Check Title similarity
            sim_title = similarity(current_title, kept_title)
            
            # If titles are very similar
            if sim_title > 0.85:
                is_dup = True
                ids_to_delete.add(item["id"])
                print(f"[Fuzzy Title {sim_title:.2f}] Deleting: {item.get('title')} (ID: {item['id']})")
                print(f"   -> Similar to: {kept.get('title')} (ID: {kept['id']})")
                break
            
            # If titles are somewhat similar but snippet is identical
            if sim_title > 0.6 and current_snippet and kept_snippet:
                sim_snippet = similarity(current_snippet, kept_snippet)
                if sim_snippet > 0.9:
                    is_dup = True
                    ids_to_delete.add(item["id"])
                    print(f"[Fuzzy Mix T:{sim_title:.2f}/S:{sim_snippet:.2f}] Deleting: {item.get('title')}")
                    break

        if not is_dup:
            kept_items.append(item)

    print(f"Found {len(ids_to_delete)} total duplicates to delete.")
    
    if not ids_to_delete:
        print("No duplicates found.")
        return

    # Batch delete
    id_list = list(ids_to_delete)
    batch_size = 100
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i+batch_size]
        print(f"Deleting batch {i // batch_size + 1} ({len(batch)} items)...")
        try:
            supabase.table("news").delete().in_("id", batch).execute()
        except Exception as e:
            print(f"Error deleting batch: {e}")

    print("Cleanup complete.")

if __name__ == "__main__":
    clean_duplicates()
