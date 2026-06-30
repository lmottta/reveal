import sys
import os
import time
import random
import unicodedata
import json
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
env_path = os.path.join(backend_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

from app.db.session import SessionLocal, engine
from app.models.search import Search, News
from app.models.lawsuit import Lawsuit
from app.db.base import Base
from app.core.constants import STATE_COORDS
from app.utils.enricher import enrich_news_item, clean_text

Base.metadata.create_all(bind=engine)
print("Database initialized.")

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
    "VIOLENCIA SEXUAL CONTRA MULHERES",
    "ASSEDIO SEXUAL",
    "IMPORTUNACAO SEXUAL",
    "AMEACA DE ESTUPRO",
    "SEXUAL",
    "ABUSO",
    "ESTUPRO"
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
    "sentença condenatória stupro",
    "violência sexual",
    "assedio sexual",
    "crime sexual"
]

NEWS_SOURCES = {
    "g1": {
        "name": "G1",
        "base_url": "https://g1.globo.com/",
        "search_url": "https://g1.globo.com/busca/?q={}",
        "rss": "https://g1.globo.com/rss/g1/",
        "regions": ["sp", "rj", "mg", "ba", "pe", "ce", "pr", "rs", "df", "go"]
    },
    "uol": {
        "name": "UOL",
        "base_url": "https://www.uol.com.br/",
        "search_url": "https://www.uol.com.br/search?q={}",
        "rss": None,
        "regions": None
    },
    "terra": {
        "name": "Terra",
        "base_url": "https://www.terra.com.br/",
        "search_url": "https://www.terra.com.br/busca/{}",
        "rss": "https://www.terra.com.br/rss/",
        "regions": None
    },
    "folha": {
        "name": "Folha de S.Paulo",
        "base_url": "https://www.folha.uol.com.br/",
        "search_url": "https://busca.folha.uol.com.br/search?q={}",
        "rss": "https://www.folha.uol.com.br/feed.xml",
        "regions": None
    },
    "r7": {
        "name": "R7",
        "base_url": "https://www.r7.com/",
        "search_url": "https://www.r7.com/busca?term={}",
        "rss": "https://www.r7.com/feed/rss/",
        "regions": ["sp", "rj", "mg", "ba", "ce", "pr", "rs", "df"]
    },
    "band": {
        "name": "Band",
        "base_url": "https://www.band.uol.com.br/",
        "search_url": "https://www.band.uol.com.br/busca?q={}",
        "rss": None,
        "regions": None
    },
    "estadao": {
        "name": "Estadão",
        "base_url": "https://www.estadao.com.br/",
        "search_url": "https://www.estadao.com.br/busca?q={}",
        "rss": "https://www.estadao.com.br/feed/rss/",
        "regions": None
    },
    "correio": {
        "name": "Correio Braziliense",
        "base_url": "https://www.correiobraziliense.com.br/",
        "search_url": "https://www.correiobraziliense.com.br/busca?term={}",
        "rss": "https://www.correiobraziliense.com.br/rss/",
        "regions": None
    },
    "oglobo": {
        "name": "O Globo",
        "base_url": "https://oglobo.globo.com/",
        "search_url": "https://oglobo.globo.com/busca/{}",
        "rss": "https://oglobo.globo.com/rss/feed/",
        "regions": None
    },
    "gazeta": {
        "name": "Gazeta do Povo",
        "base_url": "https://www.gazetadopovo.com.br/",
        "search_url": "https://www.gazetadopovo.com.br/busca/?q={}",
        "rss": "https://www.gazetadopovo.com.br/feed/rss/",
        "regions": None
    },
    "diario": {
        "name": "Diário do Grande ABC",
        "base_url": "https://dgabc.com.br/",
        "search_url": "https://dgabc.com.br/busca/{}",
        "rss": None,
        "regions": None
    },
    "zerohora": {
        "name": "Zero Hora",
        "base_url": "https://gauchazh.clicrbs.com.br/",
        "search_url": "https://gauchazh.clicrbs.com.br/busca/{}",
        "rss": "https://gauchazh.clicrbs.com.br/rss/",
        "regions": None
    }
}

BRASIL_CITIES = [
    {"city": "São Paulo", "state": "SP"},
    {"city": "Campinas", "state": "SP"},
    {"city": "Santos", "state": "SP"},
    {"city": "Ribeirão Preto", "state": "SP"},
    {"city": "Sorocaba", "state": "SP"},
    {"city": "São José dos Campos", "state": "SP"},
    {"city": "Osasco", "state": "SP"},
    {"city": "Guarulhos", "state": "SP"},
    {"city": "São Bernardo do Campo", "state": "SP"},
    {"city": "Santo André", "state": "SP"},
    {"city": "Rio de Janeiro", "state": "RJ"},
    {"city": "Niterói", "state": "RJ"},
    {"city": "São Gonçalo", "state": "RJ"},
    {"city": "Duque de Caxias", "state": "RJ"},
    {"city": "Nova Iguaçu", "state": "RJ"},
    {"city": "Belford Roxo", "state": "RJ"},
    {"city": "Campos dos Goytacazes", "state": "RJ"},
    {"city": "Belo Horizonte", "state": "MG"},
    {"city": "Uberlândia", "state": "MG"},
    {"city": "Contagem", "state": "MG"},
    {"city": "Juiz de Fora", "state": "MG"},
    {"city": "Betim", "state": "MG"},
    {"city": "Curitiba", "state": "PR"},
    {"city": "Londrina", "state": "PR"},
    {"city": "Maringá", "state": "PR"},
    {"city": "Ponta Grossa", "state": "PR"},
    {"city": "Cascavel", "state": "PR"},
    {"city": "Foz do Iguaçu", "state": "PR"},
    {"city": "Porto Alegre", "state": "RS"},
    {"city": "Caxias do Sul", "state": "RS"},
    {"city": "Pelotas", "state": "RS"},
    {"city": "Canoas", "state": "RS"},
    {"city": "Florianópolis", "state": "SC"},
    {"city": "Joinville", "state": "SC"},
    {"city": "Blumenau", "state": "SC"},
    {"city": "São José", "state": "SC"},
    {"city": "Brasília", "state": "DF"},
    {"city": "Taguatinga", "state": "DF"},
    {"city": "Ceilândia", "state": "DF"},
    {"city": "Goiânia", "state": "GO"},
    {"city": "Anápolis", "state": "GO"},
    {"city": "Aparecida de Goiânia", "state": "GO"},
    {"city": "Cuiabá", "state": "MT"},
    {"city": "Várzea Grande", "state": "MT"},
    {"city": "Rondonópolis", "state": "MT"},
    {"city": "Campo Grande", "state": "MS"},
    {"city": "Dourados", "state": "MS"},
    {"city": "Salvador", "state": "BA"},
    {"city": "Feira de Santana", "state": "BA"},
    {"city": "Vitória da Conquista", "state": "BA"},
    {"city": "Camaçari", "state": "BA"},
    {"city": "Recife", "state": "PE"},
    {"city": "Jaboatão dos Guararapes", "state": "PE"},
    {"city": "Olinda", "state": "PE"},
    {"city": "Caruaru", "state": "PE"},
    {"city": "Fortaleza", "state": "CE"},
    {"city": "Caucaia", "state": "CE"},
    {"city": "Juazeiro do Norte", "state": "CE"},
    {"city": "Maracanaú", "state": "CE"},
    {"city": "Natal", "state": "RN"},
    {"city": "Mossoró", "state": "RN"},
    {"city": "Parnamirim", "state": "RN"},
    {"city": "João Pessoa", "state": "PB"},
    {"city": "Campina Grande", "state": "PB"},
    {"city": "Maceió", "state": "AL"},
    {"city": "Arapiraca", "state": "AL"},
    {"city": "Teresina", "state": "PI"},
    {"city": "Parnaíba", "state": "PI"},
    {"city": "São Luís", "state": "MA"},
    {"city": "Imperatriz", "state": "MA"},
    {"city": "São José de Ribamar", "state": "MA"},
    {"city": "Belém", "state": "PA"},
    {"city": "Ananindeua", "state": "PA"},
    {"city": "Santarém", "state": "PA"},
    {"city": "Marabá", "state": "PA"},
    {"city": "Manaus", "state": "AM"},
    {"city": "Parintins", "state": "AM"},
    {"city": "Itacoatiara", "state": "AM"},
    {"city": "Rio Branco", "state": "AC"},
    {"city": "Cruzeiro do Sul", "state": "AC"},
    {"city": "Porto Velho", "state": "RO"},
    {"city": "Ji-Paraná", "state": "RO"},
    {"city": "Boa Vista", "state": "RR"},
    {"city": "Macapá", "state": "AP"},
    {"city": "Santana", "state": "AP"},
    {"city": "Palmas", "state": "TO"},
    {"city": "Araguaina", "state": "TO"},
    {"city": "Vitória", "state": "ES"},
    {"city": "Vila Velha", "state": "ES"},
    {"city": "Serra", "state": "ES"},
    {"city": "Cariacica", "state": "ES"},
    {"city": "Aracaju", "state": "SE"},
    {"city": "Nossa Senhora do Socorro", "state": "SE"},
    {"city": "Campo Grande", "state": "AL"},
    {"city": "São Paulo", "state": "SP"},
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

def infer_location(text: str) -> dict:
    text_upper = text.upper()
    for uf, data in STATE_COORDS.items():
        if uf in text_upper:
            return {"state": uf, "city": None}
    
    for city_data in BRASIL_CITIES:
        city_upper = city_data["city"].upper()
        if city_upper in text_upper:
            return {"state": city_data["state"], "city": city_data["city"]}
    
    return {"state": None, "city": None}

def fetch_from_google_rss(query: str, max_items: int = 50) -> list:
    items = []
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        with urlopen(request, timeout=20) as response:
            payload = response.read()
        root = ET.fromstring(payload)
        channel = root.find("channel")
        if channel is None:
            return items
        for node in channel.findall("item")[:max_items]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = (node.findtext("pubDate") or "").strip()
            source = "Google News"
            source_node = node.find("{http://search.yahoo.com/mrss/}source")
            if source_node is not None and source_node.text:
                source = source_node.text.strip()
            
            clean_title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
            snippet = re.sub(r"<[^>]+>", " ", description)
            snippet = re.sub(r"\s+", " ", snippet).strip()
            
            if clean_title and link:
                item = enrich_news_item({
                    "title": clean_title,
                    "url": link,
                    "source": source,
                    "snippet": snippet[:500] if snippet else "",
                    "published_date": pub_date,
                    "image_url": None
                })
                items.append(item)
    except Exception as e:
        print(f"  RSS Error for '{query}': {e}")
    return items

def fetch_from_source_rss(source_key: str, max_items: int = 20) -> list:
    source = NEWS_SOURCES.get(source_key)
    if not source or not source.get("rss"):
        return []
    
    items = []
    try:
        request = Request(source["rss"], headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            payload = response.read()
        root = ET.fromstring(payload)
        
        for node in root.findall(".//item")[:max_items]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = (node.findtext("pubDate") or "").strip()
            
            snippet = re.sub(r"<[^>]+>", " ", description)
            snippet = re.sub(r"\s+", " ", snippet).strip()[:300]
            
            if title and link:
                item = enrich_news_item({
                    "title": title,
                    "url": link,
                    "source": source["name"],
                    "snippet": snippet[:500],
                    "published_date": pub_date,
                    "image_url": None
                })
                items.append(item)
    except Exception as e:
        print(f"  RSS Error for {source_key}: {e}")
    
    return items

def collect_news_v2():
    db = SessionLocal()
    total_collected = 0
    target = 5000
    seen_urls = set()
    
    existing_urls = db.query(News.url).all()
    for url_tuple in existing_urls:
        if url_tuple[0]:
            seen_urls.add(normalize_url(url_tuple[0]))
    
    print(f"Starting Mass Collection V2. Target: {target} records.")
    print(f"Already have {len(seen_urls)} unique URLs in database.")
    
    search_record = Search(
        query="MASS_COLLECTION_V2",
        tribunal="System"
    )
    db.add(search_record)
    db.commit()
    db.refresh(search_record)
    
    search_variants = []
    for term in SEARCH_TERMS:
        search_variants.append(term)
        for uf in STATE_COORDS.keys():
            search_variants.append(f"{term} {uf}")
    
    random.shuffle(search_variants)
    
    rss_sources = ["g1", "uol", "terra", "folha", "r7", "band", "estadao", "correio", "oglobo", "gazeta", "zerohora"]
    
    print("\n=== Phase 1: Collecting from RSS Feeds ===")
    for source_key in rss_sources:
        if total_collected >= target:
            break
        print(f"Collecting from {source_key} RSS...")
        items = fetch_from_source_rss(source_key, max_items=30)
        
        for item in items:
            url = normalize_url(item.get("url", ""))
            if not url or url in seen_urls:
                continue
            
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if not is_relevant_content(text):
                continue
            
            loc = infer_location(f"{item.get('title', '')} {item.get('snippet', '')}")
            item["city"] = loc.get("city")
            item["state"] = loc.get("state")
            
            try:
                news_item = News(
                    search_id=search_record.id,
                    title=item["title"],
                    url=url,
                    source=item["source"],
                    snippet=item["snippet"],
                    image_url=item.get("image_url"),
                    published_date=item.get("published_date"),
                    city=item.get("city"),
                    state=item.get("state")
                )
                db.add(news_item)
                seen_urls.add(url)
                total_collected += 1
            except Exception as e:
                pass
        
        db.commit()
        print(f"  Total collected so far: {total_collected}")
        time.sleep(random.uniform(1, 3))
    
    print(f"\n=== Phase 2: Collecting from Google News RSS (Search Terms) ===")
    for query_term in search_variants:
        if total_collected >= target:
            break
        
        print(f"Searching: {query_term}...")
        items = fetch_from_google_rss(query_term, max_items=30)
        
        new_in_batch = 0
        for item in items:
            url = normalize_url(item.get("url", ""))
            if not url or url in seen_urls:
                continue
            
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if not is_relevant_content(text):
                continue
            
            loc = infer_location(f"{item.get('title', '')} {item.get('snippet', '')}")
            item["city"] = loc.get("city")
            item["state"] = loc.get("state")
            
            if not item["state"]:
                for uf in STATE_COORDS.keys():
                    if uf in query_term.upper():
                        item["state"] = uf
                        break
            
            try:
                news_item = News(
                    search_id=search_record.id,
                    title=item["title"],
                    url=url,
                    source=item["source"],
                    snippet=item["snippet"],
                    image_url=item.get("image_url"),
                    published_date=item.get("published_date"),
                    city=item.get("city"),
                    state=item.get("state")
                )
                db.add(news_item)
                seen_urls.add(url)
                total_collected += 1
                new_in_batch += 1
            except Exception as e:
                pass
        
        if new_in_batch > 0:
            db.commit()
            print(f"  +{new_in_batch} new items. Total: {total_collected}")
        
        time.sleep(random.uniform(1, 3))
    
    print(f"\n=== Phase 3: Collecting from Major City Portals ===")
    for city_data in BRASIL_CITIES[:50]:
        if total_collected >= target:
            break
        
        city = city_data["city"]
        state = city_data["state"]
        
        for term in SEARCH_TERMS[:3]:
            query = f"{term} {city} {state}"
            print(f"Searching: {query}...")
            
            items = fetch_from_google_rss(query, max_items=15)
            
            new_in_batch = 0
            for item in items:
                url = normalize_url(item.get("url", ""))
                if not url or url in seen_urls:
                    continue
                
                text = f"{item.get('title', '')} {item.get('snippet', '')}"
                if not is_relevant_content(text):
                    continue
                
                item["city"] = city
                item["state"] = state
                
                try:
                    news_item = News(
                        search_id=search_record.id,
                        title=item["title"],
                        url=url,
                        source=item["source"],
                        snippet=item["snippet"],
                        image_url=item.get("image_url"),
                        published_date=item.get("published_date"),
                        city=city,
                        state=state
                    )
                    db.add(news_item)
                    seen_urls.add(url)
                    total_collected += 1
                    new_in_batch += 1
                except Exception as e:
                    pass
            
            if new_in_batch > 0:
                db.commit()
                print(f"  +{new_in_batch} new items. Total: {total_collected}")
            
            time.sleep(random.uniform(0.5, 2))
    
    print(f"\n=== Collection Complete ===")
    print(f"Total collected: {total_collected}")
    
    db.close()

if __name__ == "__main__":
    collect_news_v2()
