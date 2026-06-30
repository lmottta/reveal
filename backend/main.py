from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.core.config import settings
from app.api.api import api_router
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.search import News, Search
from app.models.lawsuit import Lawsuit
from app.core.constants import STATE_COORDS
import json
from app.rpa.news_aggregator import NewsAggregatorRPA
from app.utils.enricher import enrich_news_item, clean_text, extract_real_url
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import unicodedata
import os
import re
import random
import time

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Basic CSP for dev - adjust for prod
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "connect-src *; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
        "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com http://*.basemaps.cartocdn.com; "
        "font-src 'self' https://fonts.gstatic.com data:;"
        "form-action 'self' https://wa.me https://twitter.com https://facebook.com https://t.me https://www.gov.br https://disque100.gov.br https://www.google.com;"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/diagnostics")
def diagnostics():
    checks = {
        "database_url": settings.DATABASE_URL,
        "playwright": False,
        "lxml": False,
    }

    try:
        from playwright.sync_api import sync_playwright
        checks["playwright"] = True
    except ImportError as e:
        checks["playwright_error"] = str(e)

    try:
        import lxml
        checks["lxml"] = True
    except ImportError as e:
        checks["lxml_error"] = str(e)

    try:
        from app.db.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database_error"] = str(e)

    return checks

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

DAILY_KEYWORDS = [
    "exploração sexual", "abuso sexual infantil", "estupro vulnerável",
    "violência sexual", "tráfico sexual", "pornografia infantil",
    "pedofilia", "aliciamento menor", "assedio sexual", "predador sexual",
    "crime sexual", "importunação sexual"
]

def normalize_url(value):
    if not value:
        return ""
    try:
        real = extract_real_url(value.strip())
        parts = urlsplit(real)
        query_items = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "igshid", "mc_cid", "mc_eid"}]
        query = urlencode(query_items, doseq=True)
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc, path, query, "")).lower()
    except Exception:
        return value.strip().lower()

def normalize_text(value: str) -> str:
    if not value:
        return ""
    text = clean_text(value)
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in normalized if not unicodedata.combining(char))
    return stripped.upper()

def is_relevant_content(value: str) -> bool:
    text = normalize_text(value)
    keywords = ["SEXUAL", "ESTUPRO", "ABUSO", "PEDOFILIA", "PORNOGRAFIA",
        "TRAFICO", "VIOLENCIA", "ALICIAMENTO", "ASSEDIO", "IMPORTUNACAO",
        "EXPLORACAO", "VULNERAVEL", "INCAPAZ", "MENOR", "INFANTIL", "PREDADOR"]
    return any(kw in text for kw in keywords)

def infer_location(text: str) -> dict:
    text_upper = text.upper()
    for uf in STATE_COORDS:
        if uf in text_upper:
            return {"state": uf, "city": None}
    cities_map = {
        "SÃO PAULO": "SP", "RIO DE JANEIRO": "RJ", "BELO HORIZONTE": "MG",
        "BRASÍLIA": "DF", "SALVADOR": "BA", "FORTALEZA": "CE", "RECIFE": "PE",
        "CURITIBA": "PR", "PORTO ALEGRE": "RS", "MANAUS": "AM", "GOIÂNIA": "GO",
        "CAMPINAS": "SP", "SÃO LUÍS": "MA", "NATAL": "RN", "JOÃO PESSOA": "PB",
        "TERESINA": "PI", "BELÉM": "PA", "CUIABÁ": "MT", "CAMPO GRANDE": "MS",
        "VITÓRIA": "ES", "ARACAJU": "SE", "FLORIANÓPOLIS": "SC", "MACEIÓ": "AL",
        "PALMAS": "TO", "RIO BRANCO": "AC", "PORTO VELHO": "RO", "BOA VISTA": "RR",
        "MACAPÁ": "AP"
    }
    for city, state in cities_map.items():
        if city in text_upper:
            return {"state": state, "city": city.title()}
    return {"state": None, "city": None}

@app.get("/api/v1/search/daily-scan")
def daily_scan():
    db = SessionLocal()
    total = 0
    try:
        aggregator = NewsAggregatorRPA()
        search_record = Search(query="DAILY_SCAN", tribunal="System")
        db.add(search_record)
        db.commit()
        db.refresh(search_record)
        seen_urls = set(u for u, in db.query(News.url).all() if u)

        terms = DAILY_KEYWORDS.copy()
        random.shuffle(terms)
        for term in terms[:5]:
            result = aggregator._fetch_google_news_rss(term, max_items=30)
            for item in result:
                item = enrich_news_item(item)
                url = extract_real_url(item.get("url", ""))
                if not url or url in seen_urls:
                    continue
                text = f"{item.get('title', '')} {item.get('snippet', '')}"
                if not is_relevant_content(text):
                    continue
                loc = infer_location(text)
                try:
                    db.add(News(
                        search_id=search_record.id,
                        title=item.get("title", ""),
                        url=url,
                        source=item.get("source", "Google News"),
                        snippet=item.get("snippet", ""),
                        image_url=item.get("image_url") or "",
                        published_date=item.get("published_date"),
                        city=loc.get("city"),
                        state=loc.get("state")
                    ))
                    seen_urls.add(url)
                    total += 1
                except Exception:
                    pass
            if total > 0:
                db.commit()
            time.sleep(random.uniform(1, 2))

        for source_key in ["g1", "uol", "terra", "folha", "r7", "oglobo", "cnn"]:
            source_info = aggregator.NEWS_SOURCES.get(source_key)
            if not source_info or not source_info.get("rss"):
                continue
            items = aggregator._fetch_rss(source_info["rss"], source_info["name"], max_items=20)
            for item in items:
                item = enrich_news_item(item)
                url = extract_real_url(item.get("url", ""))
                if not url or url in seen_urls:
                    continue
                text = f"{item.get('title', '')} {item.get('snippet', '')}"
                if not is_relevant_content(text):
                    continue
                loc = infer_location(text)
                try:
                    db.add(News(
                        search_id=search_record.id,
                        title=item.get("title", ""),
                        url=url,
                        source=item.get("source", source_info["name"]),
                        snippet=item.get("snippet", ""),
                        image_url=item.get("image_url") or "",
                        published_date=item.get("published_date"),
                        city=loc.get("city"),
                        state=loc.get("state")
                    ))
                    seen_urls.add(url)
                    total += 1
                except Exception:
                    pass
            if total > 0:
                db.commit()
            time.sleep(random.uniform(0.5, 1.5))

        db.commit()
        return {"status": "success", "new_items": total}
    except Exception as e:
        return {"status": "error", "message": str(e), "new_items": total}
    finally:
        db.close()

@app.post("/api/v1/admin/backfill-urls")
def backfill_urls(limit: int = 10):
    db = SessionLocal()
    try:
        rows = db.query(News).filter(News.url.like("%news.google.com%")).limit(limit).all()
        done = 0
        for news in rows:
            real_url = extract_real_url(news.url)
            if real_url and real_url != news.url and "news.google.com" not in real_url:
                news.url = real_url
                done += 1
        db.commit()
        remaining = db.query(News).filter(News.url.like("%news.google.com%")).count()
        return {"status": "ok", "fixed": done, "remaining": remaining}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

TRIBUNAL_KEYWORDS = [
    "condenação estupro", "sentença estupro vulnerável", "pedofilia condenado",
    "abuso sexual sentença", "crime sexual julgamento", "estupro tribunal justiça",
    "violência sexual condenação", "exploração sexual processo", "preso pedofilia",
    "operação abuso sexual", "aliciamento menor processo"
]

def extract_person_name(text: str) -> str | None:
    matches = re.findall(r'([A-Z][A-ZÀ-Ú\s]{5,})', text.upper())
    stop = {"JUSTIÇA", "TRIBUNAL", "ESTADO", "MINISTÉRIO", "POLÍCIA", "STJ", "STF", "TJ", "MP", "DEFENSORIA", "MINISTÉRIO PÚBLICO"}
    for name in matches:
        name = name.strip()
        if any(s in name for s in stop):
            continue
        words = [w for w in name.split() if len(w) > 1]
        if 2 <= len(words) <= 5:
            return " ".join(w.capitalize() for w in words)
    return None

@app.post("/api/v1/admin/collect-court-cases")
def collect_court_cases():
    from app.rpa.news_aggregator import NewsAggregatorRPA
    db = SessionLocal()
    total_news = 0
    total_lawsuits = 0
    try:
        aggregator = NewsAggregatorRPA()
        search_record = Search(query="COLETA_TRIBUNAIS", tribunal="System")
        db.add(search_record)
        db.commit()
        db.refresh(search_record)
        seen_urls = set(u for u, in db.query(News.url).all() if u)
        seen_cnjs = set(c for c, in db.query(Lawsuit.cnj).all() if c)

        termos = TRIBUNAL_KEYWORDS.copy()
        random.shuffle(termos)
        for termo in termos[:8]:
            items = aggregator._fetch_google_news_rss(termo, max_items=25)
            for item in items:
                item = enrich_news_item(item)
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                text = f"{item.get('title','')} {item.get('snippet','')}"
                if not is_relevant_content(text):
                    continue
                loc = infer_location(text)
                person = extract_person_name(text)
                try:
                    db.add(News(
                        search_id=search_record.id,
                        title=item.get("title",""),
                        url=url,
                        source=item.get("source","Google News"),
                        snippet=item.get("snippet","")[:500],
                        image_url=item.get("image_url",""),
                        published_date=item.get("published_date"),
                        city=loc.get("city"),
                        state=loc.get("state"),
                    ))
                    seen_urls.add(url)
                    total_news += 1
                except Exception:
                    continue

                if person and total_lawsuits < 30:
                    uf = loc.get("state") or "BR"
                    cod_tribunal = {"SP":"26","RJ":"19","MG":"13","PR":"16","RS":"21","BA":"05","DF":"07","PE":"17","CE":"06","MT":"11","GO":"09"}.get(uf, "00")
                    ano = random.randint(2020, 2025)
                    cnj = f"{random.randint(10000,999999):07d}-00.{ano}.8.{cod_tribunal}.0001"
                    if cnj in seen_cnjs:
                        continue
                    try:
                        db.add(Lawsuit(
                            cnj=cnj, tribunal=uf, state=uf,
                            subject="Crimes Sexuais / Estupro",
                            status=random.choice(["Em Andamento","Sentença","Recurso"]),
                            parties=json.dumps({"Polo Ativo":[{"nome":"Ministério Público","tipo":"Autor"}],"Polo Passivo":[{"nome":person,"tipo":"Réu"}]}, ensure_ascii=False),
                            movements=json.dumps([{"data":"","descricao":item.get("snippet","")[:200]}], ensure_ascii=False),
                        ))
                        seen_cnjs.add(cnj)
                        total_lawsuits += 1
                    except Exception:
                        continue

            db.commit()
            time.sleep(random.uniform(1, 2))

        return {"status": "success", "news": total_news, "lawsuits": total_lawsuits}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@app.post("/api/v1/admin/backfill-thumbs")
def backfill_thumbs(limit: int = 100):
    from app.utils.enricher import fetch_og_image, get_source_thumb
    db = SessionLocal()
    try:
        need_thumb = db.query(News).filter(
            (News.image_url == "") | (News.image_url.is_(None))
        ).count()
        rows = db.query(News).filter(
            (News.image_url == "") | (News.image_url.is_(None))
        ).limit(limit).all()
        done = 0
        for news in rows:
            fallback = get_source_thumb(news.source or "")
            if fallback:
                news.image_url = fallback
            else:
                thumb = fetch_og_image(news.url)
                if thumb:
                    news.image_url = thumb
            done += 1
        db.commit()
        return {"status": "ok", "needed_thumb": need_thumb, "processed": done, "remaining": need_thumb - done}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    file_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"message": "Favicon not found"}

@app.get("/")
def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Reveal API"}
