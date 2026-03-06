from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import or_, cast, String, text
from sqlalchemy.orm import Session
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from app.rpa.tjsp import TJSPRPA
from app.rpa.tjmt import TJMTRPA
from app.rpa.google_news import GoogleNewsRPA
from app.rpa.google_web import GoogleWebRPA
from app.db.session import SessionLocal
from app.models.search import Search, SearchResult, News
from app.api.endpoints.stats import TRIBUNAL_TO_STATE, COORDS, CNJ_CODE_MAP
import json
import unicodedata
import re

router = APIRouter()

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

def normalize_url(value: str) -> str:
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

def normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.upper()

def is_relevant_content(value: str) -> bool:
    text = normalize_text(value)
    return any(keyword in text for keyword in RELEVANT_KEYWORDS)

def parse_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [term.strip() for term in raw.replace(",", "|").split("|") if term.strip()]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def search_local_db(query: str, db: Session) -> dict:
    """
    Busca na base local (News e SearchResult) antes de ir para externo.
    """
    local_results = {"results": [], "news": []}
    
    # 1. Buscar em News
    news_items = db.query(News).filter(
        or_(
            News.title.ilike(f"%{query}%"),
            News.snippet.ilike(f"%{query}%"),
            News.url.ilike(f"%{query}%")
        )
    ).all()
    
    for n in news_items:
        local_results["news"].append({
            "title": n.title,
            "url": n.url,
            "source": n.source,
            "snippet": n.snippet,
            "published_date": n.published_date,
            "image_url": n.image_url,
            "city": n.city,
            "state": n.state,
            "origin": "local_db"
        })

    # 2. Buscar em SearchResult (conteúdo JSON)
    # Tenta converter para string para busca genérica
    # Nota: Isso pode ser lento em bases grandes sem índice GIN/FullText, mas para MVP local serve.
    search_results = db.query(SearchResult).filter(
        cast(SearchResult.content, String).ilike(f"%{query}%")
    ).order_by(SearchResult.created_at.desc()).limit(50).all()

    seen_ids = set()
    
    for sr in search_results:
        content = sr.content
        if not content or "results" not in content:
            continue
            
        for item in content["results"]:
            # Verifica se o item realmente dá match com a query (pois o ilike foi no JSON inteiro)
            item_str = json.dumps(item).upper()
            if query.upper() in item_str:
                # Criar um ID único para evitar duplicatas na visualização
                unique_id = item.get("processo") or item.get("numero_processo") or item.get("id") or str(hash(item_str))
                
                # CORREÇÃO DE INTEGRIDADE: Validar Tribunal pelo CNJ se disponível
                # Se o ID for CNJ, forçar o tribunal correto
                cnj_clean = re.sub(r"\D", "", unique_id)
                if len(cnj_clean) == 20:
                    # NNNNNNN-DD.AAAA.J.TR.OOOO -> TR está na posição 14-16 (index 13:15 na string limpa? Não. )
                    # Formato limpo: NNNNNNNDDAAAAQTROOOO
                    # TR está nos indices 13:15 (0-based) ?
                    # Ex: 8933407-11.2016.8.14.4071 -> 89334071120168144071
                    # 0123456 78 9012 3 45
                    # TR = 14. Correto.
                    tr_id = cnj_clean[14:16]
                    correct_tribunal = CNJ_CODE_MAP.get(tr_id)
                    if correct_tribunal:
                        item["tribunal"] = correct_tribunal
                
                if unique_id not in seen_ids:
                    item["origin"] = "local_db"
                    local_results["results"].append(item)
                    seen_ids.add(unique_id)

    return local_results

@router.get("/")
def search_process(query: str, db: Session = Depends(get_db)):
    """
    Inicia uma consulta assistida.
    Prioriza base local, depois tenta externo se possível.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 0. Busca Local Primeiro
    local_data = search_local_db(query, db)
    
    # Se encontrou exatamente o processo buscado na base local, podemos retornar ou mesclar.
    # A política é "extender para externo". Então continuamos, mas já temos algo.

    # Identificar Tribunal pelo CNJ
    tribunal_name = "TJSP" # Default
    rpa_instance = None
    
    # Regex para CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
    cnj_match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.(\d{2})\.\d{4}", query)
    
    if cnj_match:
        tr_id = cnj_match.group(1)
        tribunal_name = CNJ_CODE_MAP.get(tr_id, f"TJ{tr_id}")
        
        if tr_id == "11": # MT
            rpa_instance = TJMTRPA()
        elif tr_id == "26": # SP
            rpa_instance = TJSPRPA()
        else:
            # Tribunal não implementado para RPA externo
            rpa_instance = None
            print(f"Tribunal {tribunal_name} (ID {tr_id}) não possui RPA implementado. Retornando apenas dados locais.")
    else:
        # Se não é CNJ, tenta inferir ou usa padrão (busca textual)
        if "8.11" in query:
            tribunal_name = "TJMT"
            rpa_instance = TJMTRPA()
        else:
            # Default para SP se for busca genérica por nome (ou implementar busca multi-tribunal futuramente)
            tribunal_name = "TJSP"
            rpa_instance = TJSPRPA()

    # Registrar a busca
    search_record = Search(query=query, tribunal=f"{tribunal_name}+News")
    db.add(search_record)
    db.commit()
    db.refresh(search_record)

    # 1. Executar RPA Tribunal (Se disponível)
    rpa_result = {"results": [], "status": "skipped"}
    
    if rpa_instance:
        try:
            rpa_result = rpa_instance.search(query)
            filtered_results = []
            for item in rpa_result.get("results", []):
                text = f"{item.get('classe', '')} {item.get('assunto', '')} {item.get('descricao', '')} {item.get('raw', '')}"
                if is_relevant_content(text):
                    # Assegurar tribunal correto no item se for CNJ
                    if cnj_match:
                         tr_id_res = cnj_match.group(1)
                         correct_tribunal_res = CNJ_CODE_MAP.get(tr_id_res)
                         if correct_tribunal_res:
                            item["tribunal"] = correct_tribunal_res
                    filtered_results.append(item)
            rpa_result["results"] = filtered_results

            # Salvar novos resultados no banco
            if filtered_results:
                search_result_db = SearchResult(
                    search_id=search_record.id,
                    content=rpa_result
                )
                db.add(search_result_db)
                db.commit()

        except Exception as e:
            print(f"Erro {tribunal_name}: {e}")
            rpa_result = {"status": "error", "error": str(e), "results": []}
    else:
        rpa_result["msg"] = f"Tribunal {tribunal_name} não suportado para busca externa automática. Exibindo registros locais."

    # 2. Executar RPA Web (Projuris, Jusbrasil, Escavador)
    web_rpa = GoogleWebRPA()
    web_result = {"results": [], "status": "skipped"}
    try:
        web_result = web_rpa.search(query)
        filtered_web = []
        for item in web_result.get("results", []):
            text = f"{item.get('classe', '')} {item.get('assunto', '')} {item.get('descricao', '')}"
            if is_relevant_content(text):
                # Normalizar tribunal
                if cnj_match:
                    tr_id_res = cnj_match.group(1)
                    correct_tribunal_res = CNJ_CODE_MAP.get(tr_id_res)
                    if correct_tribunal_res:
                        item["tribunal"] = correct_tribunal_res
                filtered_web.append(item)
        web_result["results"] = filtered_web

        if filtered_web:
             search_result_web = SearchResult(
                search_id=search_record.id,
                content=web_result
             )
             db.add(search_result_web)
             db.commit()
    except Exception as e:
        print(f"Erro Web: {e}")
        web_result = {"status": "error", "error": str(e), "results": []}

    # 3. Executar RPA Google News
    # (Sempre executa para trazer novidades, a menos que o usuário queira só local - mas o requisito é extender)
    news_rpa = GoogleNewsRPA()
    news_result = {"results": [], "status": "pending"}

    try:
        news_result = news_rpa.search(query)
        filtered_news = []
        for item in news_result.get("results", []):
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if is_relevant_content(text):
                filtered_news.append(item)
        news_result["results"] = filtered_news

        if news_result.get("status") == "success":
            for item in news_result.get("results", []):
                exists = db.query(News).filter(News.url == item["url"]).first()
                if not exists:
                    news_item = News(
                        search_id=search_record.id,
                        title=item["title"],
                        url=item["url"],
                        source=item["source"],
                        snippet=item["snippet"],
                        image_url=item["image_url"],
                        published_date=item.get("published_date"),
                        city=item.get("city"),
                        state=item.get("state")
                    )
                    db.add(news_item)
            db.commit()

    except Exception as e:
        print(f"Erro News: {e}")
        news_result = {"status": "error", "error": str(e), "results": []}

    # Combinar resposta (Local + RPA + Web + News)
    # Deduplicar resultados judiciais (Local vs RPA vs Web)
    final_judicial = local_data["results"]
    
    # Adicionar RPA se não estiver já na lista (baseado em número do processo)
    local_ids = {x.get("processo") or x.get("numero_processo") for x in final_judicial}
    
    for item in rpa_result.get("results", []):
        pid = item.get("processo") or item.get("numero_processo")
        if pid not in local_ids:
            final_judicial.append(item)
            if pid:
                local_ids.add(pid)
    
    # Adicionar Web RPA
    for item in web_result.get("results", []):
        pid = item.get("processo") or item.get("numero_processo")
        if not pid or pid not in local_ids:
            final_judicial.append(item)
            if pid:
                local_ids.add(pid)
            
    # Deduplicar News
    final_news = local_data["news"]
    local_urls = {x.get("url") for x in final_news}
    
    for item in news_result.get("results", []):
        if item.get("url") not in local_urls:
            final_news.append(item)

    final_response = {
        "results": final_judicial,
        "news": final_news,
        "status": "success",
        "tribunal": tribunal_name,
        "msg": rpa_result.get("msg")
    }
    
    return final_response

from sqlalchemy import func

@router.delete("/clean")
def clean_duplicates(db: Session = Depends(get_db)):
    """
    Remove notícias duplicadas baseadas na URL.
    """
    duplicates = db.query(News.url, func.count(News.id)).group_by(News.url).having(func.count(News.id) > 1).all()
    
    deleted_count = 0
    for url, count in duplicates:
        items = db.query(News).filter(News.url == url).order_by(News.id.desc()).all()
        for item in items[1:]:
            db.delete(item)
            deleted_count += 1
            
    db.commit()
    return {"message": f"Removidas {deleted_count} notícias duplicadas."}

import logging

logger = logging.getLogger("uvicorn.error")

@router.post("/scan")
def news_deep_scan(db: Session = Depends(get_db)):
    """
    Realiza uma varredura massiva por casos históricos de exploração sexual e abuso de menores.
    Popula o banco de dados com os resultados encontrados.
    """
    from app.core.config import settings
    logger.info(f"Server DB URI: {settings.SQLALCHEMY_DATABASE_URI}")
    initial_count = db.query(News).count()
    logger.info(f"Initial News Count: {initial_count}")
    log_file = "scan_log.txt"
    def log(msg):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"DB URL in Scan: {db.bind.url}")
    queries = [
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
        "crime sexual contra vulneráveis"
    ]
    
    rpa = GoogleNewsRPA()
    total_found = 0
    
    for query in queries:
        try:
            log(f"Scanning query: {query}")
            # Busca profunda (10 páginas para massa de dados)
            result = rpa.search(query, max_pages=10)
            log(f"RPA Result Status: {result.get('status')}")
            
            if result.get("status") == "success":
                results_list = result.get("results", [])
                filtered_results = []
                for item in results_list:
                    text = f"{item.get('title', '')} {item.get('snippet', '')}"
                    if is_relevant_content(text):
                        filtered_results.append(item)
                results_list = filtered_results
                log(f"Found {len(results_list)} results for query '{query}'")

                # Criar registro de busca "sistema"
                search_record = Search(query=query, tribunal="GoogleNewsDeepScan")
                db.add(search_record)
                db.commit()
                db.refresh(search_record)
                log(f"Created Search Record ID: {search_record.id}")
                
                batch_count = 0
                seen_urls_in_batch = set()
                
                for item in results_list:
                    url = item["url"]
                    
                    # 1. Check duplicata no batch atual
                    if url in seen_urls_in_batch:
                        continue
                        
                    # 2. Check duplicata no banco
                    exists = db.query(News).filter(News.url == url).first()
                    if not exists:
                        news_item = News(
                            search_id=search_record.id,
                            title=item["title"],
                            url=url,
                            source=item["source"],
                            snippet=item["snippet"],
                            image_url=item["image_url"],
                            published_date=item.get("published_date"),
                            city=item.get("city"),
                            state=item.get("state")
                        )
                        db.add(news_item)
                        seen_urls_in_batch.add(url)
                        # log(f"Added to session: {item['title'][:20]}...")
                        total_found += 1
                        batch_count += 1
                
                if batch_count > 0:
                    log(f"Committing batch of {batch_count} items...")
                    try:
                        db.commit()
                        log("Committed batch successfully.")
                    except Exception as commit_error:
                        log(f"COMMIT ERROR: {commit_error}")
                        db.rollback()
                else:
                    log("No new items to commit in this batch.")
                
        except Exception as e:
            log(f"CRITICAL ERROR in scan loop: {e}")
            import traceback
            # traceback.print_exc() # Can't capture this easily without io.StringIO
            db.rollback()
            continue
            
    return {"status": "completed", "new_records": total_found}

@router.get("/catalog")
def list_catalog(
    city: str = None,
    state: str = None,
    term: str = None,
    source_type: str = "all", # all, news, judicial
    type: str = None, # Alias para compatibilidade com versões antigas ou cache
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retorna o catálogo unificado (Notícias + Processos) com filtros.
    """
    # Normalização de parâmetros para evitar conflitos de cache/versão
    final_source_type = source_type
    if type and type != "all":
        final_source_type = type
        
    results = []
    
    # 1. Buscar Notícias
    if final_source_type in ["all", "news"]:
        query = db.query(News)
        if city:
            query = query.filter(News.city.ilike(f"%{city}%"))
        if state:
            query = query.filter(News.state.ilike(f"%{state}%"))
        terms = parse_terms(term)
        if terms:
            term_filters = [
                or_(News.title.ilike(f"%{t}%"), News.snippet.ilike(f"%{t}%"))
                for t in terms
            ]
            query = query.filter(or_(*term_filters))
        
        # Increase fetch limit to allow for relevance filtering
        fetch_limit = limit * 10
        news_items = query.order_by(News.created_at.desc()).limit(fetch_limit).all()
        for n in news_items:
            if not is_relevant_content(f"{n.title} {n.snippet}"):
                continue
            results.append({
                "type": "news",
                "id": n.id,
                "title": n.title,
                "snippet": n.snippet,
                "source": n.source,
                "url": n.url,
                "image_url": n.image_url,
                "published_date": n.published_date,
                "city": n.city,
                "state": n.state,
                "created_at": n.created_at
            })

    # 2. Buscar Processos Judiciais
    if final_source_type in ["all", "judicial"]:
        # Join com Search para pegar Tribunal/Estado
        q = db.query(SearchResult, Search.tribunal).join(Search, SearchResult.search_id == Search.id)
        
        # Filtro de termo (parcial, pois o conteúdo é JSON)
        # SQLite não tem suporte nativo bom para JSON, então filtramos em memória se necessário
        # Mas podemos filtrar por data para limitar
        
        fetch_limit = limit * 10
        if city or state or term:
            fetch_limit = max(limit * 20, 1000)
        elif final_source_type == "judicial":
            fetch_limit = max(limit * 10, 500)
        
        judicial_items = q.order_by(SearchResult.created_at.desc()).limit(fetch_limit).all()
        count = 0
        
        for row, tribunal in judicial_items:
            if count >= limit:
                break
                
            data = row.content
            if not data or "results" not in data:
                continue
                
            # Determinar estado base pelo Tribunal
            base_state = "BR"
            if tribunal:
                clean_tribunal = tribunal.split('+')[0].strip().upper()
                base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "BR")
            
            # Filtrar Estado (Pré-check se o item não tiver estado explícito)
            # Mas idealmente checamos item a item
                
            for item in data["results"]:
                if count >= limit:
                    break

                # Filtro de Termo
                desc = item.get("descricao", "")
                assunto = item.get("assunto", "")
                full_text = f"{desc} {assunto} {item.get('classe', '')}"
                
                terms = parse_terms(term)
                if terms and not any(t.upper() in full_text.upper() for t in terms):
                    continue
                if not is_relevant_content(full_text):
                    continue
                
                # 1. Tentar pegar Cidade/Estado explícitos do item
                # CORREÇÃO DE INTEGRIDADE: Validar Tribunal pelo CNJ se disponível
                unique_id = item.get("processo") or item.get("numero_processo") or ""
                cnj_clean = re.sub(r"\D", "", unique_id)
                if len(cnj_clean) == 20:
                    tr_id = cnj_clean[14:16]
                    correct_tribunal = CNJ_CODE_MAP.get(tr_id)
                    if correct_tribunal:
                        item["tribunal"] = correct_tribunal
                        # Atualizar base_state se possível
                        base_state = TRIBUNAL_TO_STATE.get(correct_tribunal, base_state)

                item_city = item.get("city")
                item_state = item.get("state")
                
                final_city = "DESCONHECIDO"
                final_state = base_state

                # Lógica de Cidade
                if item_city:
                    final_city = item_city.upper()
                else:
                    # Heurística de Cidade
                    cidades_conhecidas = [k for k in COORDS.keys() if k != "DESCONHECIDO"]
                    for c in cidades_conhecidas:
                        if f" {c}" in f" {desc.upper()} " or f"DE {c}" in desc.upper() or f"COMARCA DE {c}" in desc.upper():
                             final_city = c
                             break
                
                # Lógica de Estado
                if item_state:
                    final_state = item_state.upper()

                # Filtros Finais
                if city and city.upper() not in final_city: 
                    continue
                
                if state and state.upper() != final_state:
                    continue

                results.append({
                    "type": "judicial",
                    "id": row.id, 
                    "title": item.get("classe", "Processo Judicial"),
                    "snippet": desc or assunto,
                    "source": tribunal or "TRIBUNAL",
                    "url": None,
                    "image_url": None, 
                    "published_date": item.get("data_distribuicao"),
                    "city": final_city,
                    "state": final_state,
                    "created_at": row.created_at,
                    # Campos específicos de judicial
                    "processo": item.get("processo"),
                    "classe": item.get("classe"),
                    "assunto": item.get("assunto"),
                    "foro": item.get("foro"),
                    "vara": item.get("vara"),
                    "partes": item.get("partes", [])
                })
                count += 1

    # Ordenar final por data (misturando news e judicial)
    results.sort(key=lambda x: x["created_at"] or "", reverse=True)

    def build_dedupe_key(item: dict) -> str:
        item_type = item.get("type")
        if item_type == "news":
            url = normalize_url(item.get("url") or "")
            if url:
                return f"news:{url}"
            title = (item.get("title") or "").strip().lower()
            source = (item.get("source") or "").strip().lower()
            published = str(item.get("published_date") or "").strip().lower()
            return f"news:{title}|{source}|{published}"
        raw_process = item.get("processo") or item.get("numero_processo") or item.get("id")
        process_key = re.sub(r"\D", "", str(raw_process or ""))
        if process_key:
            return f"judicial:{process_key}"
        title = (item.get("title") or "").strip().lower()
        source = (item.get("source") or "").strip().lower()
        return f"judicial:{title}|{source}"

    unique_results = []
    seen = set()
    for item in results:
        key = build_dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(item)
    
    return unique_results[:limit]

@router.delete("/clean/news")
def clean_news_duplicates(limit: int = 5000, db: Session = Depends(get_db)):
    if limit < 1 or limit > 50000:
        raise HTTPException(status_code=400, detail="Invalid limit")
    news_items = db.query(News).order_by(News.created_at.desc()).limit(limit).all()
    seen = set()
    duplicate_ids = []
    for n in news_items:
        url_key = normalize_url(n.url or "")
        if not url_key:
            title = (n.title or "").strip().lower()
            source = (n.source or "").strip().lower()
            published = (n.published_date or "").strip().lower()
            url_key = f"{title}|{source}|{published}"
        if url_key in seen:
            duplicate_ids.append(n.id)
        else:
            seen.add(url_key)
    removed = 0
    if duplicate_ids:
        removed = db.query(News).filter(News.id.in_(duplicate_ids)).delete(synchronize_session=False)
        db.commit()
    return {"removed": removed, "scanned": len(news_items)}
