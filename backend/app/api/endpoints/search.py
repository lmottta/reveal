from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import or_, cast, String, text
from sqlalchemy.orm import Session
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from app.rpa.tjsp import TJSPRPA
from app.rpa.tjmt import TJMTRPA
from app.rpa.google_news import GoogleNewsRPA
from app.rpa.google_web import GoogleWebRPA
from app.rpa.news_aggregator import NewsAggregatorRPA
from app.db.session import SessionLocal
from app.models.search import Search, SearchResult, News
from app.models.lawsuit import Lawsuit
from app.core.constants import TRIBUNAL_TO_STATE, COORDS, CNJ_CODE_MAP
import json
import unicodedata
import re
from collections import defaultdict, Counter
from datetime import datetime

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
    """Verifica se o texto contém palavras-chave relevantes"""
    if not value:
        return True
    text_upper = normalize_text(value)
    return any(keyword in text_upper for keyword in RELEVANT_KEYWORDS)

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

    # 3. Executar RPA Google News + Agregador de Múltiplas Fontes
    # Usa o agregador de notícias para buscar em múltiplos portais
    news_rpa = GoogleNewsRPA()
    news_aggregator = NewsAggregatorRPA()
    news_result = {"results": [], "status": "pending"}

    try:
        # Primeiro tenta o agregador de notícias (múltiplas fontes)
        try:
            news_result = news_aggregator.search(query, max_pages=2)
        except Exception as agg_error:
            print(f"Erro no agregador: {agg_error}")
            # Fallback para GoogleNewsRPA original
            news_result = news_rpa.search(query)
        
        filtered_news = []
        for item in news_result.get("results", []):
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if is_relevant_content(text):
                filtered_news.append(item)
        news_result["results"] = filtered_news

        if news_result.get("status") == "success":
            for item in news_result.get("results", []):
                normalized_url = normalize_url(item.get("url", ""))
                if not normalized_url:
                    continue
                exists = db.query(News).filter(News.url == normalized_url).first()
                if not exists:
                    news_item = News(
                        search_id=search_record.id,
                        title=item["title"],
                        url=normalized_url,
                        source=item["source"],
                        snippet=item["snippet"],
                        image_url=item.get("image_url"),
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
def news_deep_scan(
    terms: str | None = Query(default=None),
    states: str | None = Query(default=None),
    max_pages: int = Query(default=3, ge=1, le=10),
    per_query_limit: int = Query(default=50, ge=5, le=200),
    db: Session = Depends(get_db)
):
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
    base_queries = [
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
    custom_terms = parse_terms(terms)
    queries = custom_terms if custom_terms else base_queries
    state_list = [value.strip().upper() for value in parse_terms(states) if len(value.strip()) == 2]
    
    rpa = GoogleNewsRPA()
    total_found = 0
    
    for query in queries:
        query_variants = [query]
        if state_list:
            query_variants = [f"{query} {uf}" for uf in state_list]

        for query_term in query_variants:
            try:
                log(f"Scanning query: {query_term}")
                result = rpa.search(query_term, max_pages=max_pages)
                log(f"RPA Result Status: {result.get('status')}")
                
                if result.get("status") == "success":
                    results_list = result.get("results", [])
                    filtered_results = []
                    for item in results_list:
                        text = f"{item.get('title', '')} {item.get('snippet', '')}"
                        if is_relevant_content(text):
                            filtered_results.append(item)
                    results_list = filtered_results[:per_query_limit]
                    log(f"Found {len(results_list)} results for query '{query_term}'")

                    search_record = Search(query=query_term, tribunal="GoogleNewsDeepScan")
                    db.add(search_record)
                    db.commit()
                    db.refresh(search_record)
                    log(f"Created Search Record ID: {search_record.id}")
                    
                    batch_count = 0
                    seen_urls_in_batch = set()
                    fallback_state = next((token for token in query_term.split() if len(token) == 2 and token.isalpha()), None)
                    
                    for item in results_list:
                        raw_url = item.get("url")
                        if not raw_url:
                            continue
                        url = normalize_url(raw_url)
                        
                        if url in seen_urls_in_batch:
                            continue
                            
                        exists = db.query(News).filter(News.url == url).first()
                        if not exists:
                            news_item = News(
                                search_id=search_record.id,
                                title=item.get("title"),
                                url=url,
                                source=item.get("source"),
                                snippet=item.get("snippet"),
                                image_url=item.get("image_url"),
                                published_date=item.get("published_date"),
                                city=item.get("city"),
                                state=item.get("state") or fallback_state
                            )
                            db.add(news_item)
                            seen_urls_in_batch.add(url)
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
                db.rollback()
                continue

    return {"status": "completed", "new_records": total_found}

@router.get("/catalog")
def list_catalog(
    city: str = None,
    state: str = None,
    term: str = None,
    source_type: str = "news", # all, news, judicial
    type: str = None, # Alias para compatibilidade com versões antigas ou cache
    limit: int = 100,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """
    Retorna o catálogo unificado (Notícias + Processos) com filtros.
    """
    # Normalização de parâmetros para evitar conflitos de cache/versão
    final_source_type = source_type
    if type and type != "all":
        final_source_type = type
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    if page < 1:
        page = 1
    offset = (page - 1) * limit
    page_end = offset + limit
        
    results = []
    
    # 1. Buscar Notícias
    if final_source_type in ["all", "news"]:
        query = db.query(News)
        if city:
            if city.upper() == "DESCONHECIDO":
                query = query.filter(or_(News.city == None, News.city == "", News.city.ilike("DESCONHECIDO")))
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
        fetch_limit = max(page_end * 4, limit * 20)
        news_items = query.order_by(News.created_at.desc()).limit(fetch_limit).all()
        for n in news_items:
            if not is_relevant_content(f"{n.title} {n.snippet}"):
                continue

            if city and city.upper() != "DESCONHECIDO":
                import unicodedata
                def normalize(s):
                    if not s:
                        return ""
                    return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')
                
                city_norm = normalize(city.upper())
                n_city_norm = normalize(n.city or "DESCONHECIDO")
                
                if city_norm not in n_city_norm and n_city_norm not in city_norm:
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
        
        fetch_limit = page_end * 10
        if city or state or term:
            fetch_limit = max(page_end * 20, 1000)
        elif final_source_type == "judicial":
            fetch_limit = max(page_end * 10, 500)
        
        judicial_items = q.order_by(SearchResult.created_at.desc()).limit(fetch_limit).all()
        count = 0
        target_count = page_end
        
        for row, tribunal in judicial_items:
            if count >= target_count:
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
                if count >= target_count:
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
                    cidades_conhecidas = [k for k in COORDS.keys() if k != "DESCONHECIDO"]
                    for c in cidades_conhecidas:
                        if f" {c}" in f" {desc.upper()} " or f"DE {c}" in desc.upper() or f"COMARCA DE {c}" in desc.upper():
                             final_city = c
                             break
                
                # Lógica de Estado
                if item_state:
                    final_state = item_state.upper()

                # Filtros Finais - Verificação tolerante (contém ou igual)
                city_upper = city.upper() if city else ""
                final_city_upper = final_city.upper()

                # Trata variações de acento (normaliza para comparação)
                import unicodedata
                def normalize(s):
                    if not s:
                        return ""
                    return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')

                city_norm = normalize(city_upper)
                final_city_norm = normalize(final_city_upper)

                if city:
                    if city_norm == "DESCONHECIDO":
                        if final_city_norm != "DESCONHECIDO" and final_city_norm != "":
                            continue
                    elif city_norm not in final_city_norm and final_city_norm not in city_norm:
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

        if count < target_count:
            lawsuits = db.query(Lawsuit).order_by(Lawsuit.created_at.desc()).limit(fetch_limit).all()
            for law in lawsuits:
                if count >= target_count:
                    break

                tribunal_clean = str(law.tribunal or "").split("+")[0].strip().upper()
                if len(tribunal_clean) == 2:
                    final_state = tribunal_clean
                else:
                    final_state = TRIBUNAL_TO_STATE.get(tribunal_clean, "BR")

                final_city = "DESCONHECIDO"
                if law.comarca:
                    final_city = str(law.comarca).upper().replace("COMARCA DE ", "").replace("COMARCA DO ", "").replace("COMARCA DA ", "").strip()
                elif law.court and " DE " in str(law.court).upper():
                    # extract what comes after " DE "
                    court_str = str(law.court).upper()
                    if " DE " in court_str:
                        final_city = court_str.split(" DE ", 1)[-1].strip()

                search_text = f"{law.cnj or ''} {law.judge or ''} {law.court or ''} {law.class_type or ''} {law.subject or ''} {law.parties or ''}"
                terms = parse_terms(term)
                if terms and not any(t.upper() in search_text.upper() for t in terms):
                    continue
                if not is_relevant_content(search_text):
                    continue

                if city:
                    import unicodedata
                    def normalize(s):
                        if not s:
                            return ""
                        return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')
                    city_norm = normalize(city.upper())
                    final_city_norm = normalize(final_city.upper())
                    if city_norm == "DESCONHECIDO":
                        if final_city_norm != "DESCONHECIDO" and final_city_norm != "":
                            continue
                    elif city_norm not in final_city_norm and final_city_norm not in city_norm:
                        continue
                if state and state.upper() != final_state:
                    continue

                parties_data = law.parties
                if isinstance(parties_data, str):
                    try:
                        parties_data = json.loads(parties_data)
                    except Exception:
                        parties_data = []

                results.append({
                    "type": "judicial",
                    "id": law.id,
                    "title": law.class_type or "Processo Judicial",
                    "snippet": law.subject or law.status or "",
                    "source": law.tribunal or "TRIBUNAL",
                    "url": None,
                    "image_url": None,
                    "published_date": law.distribution_date,
                    "city": final_city,
                    "state": final_state,
                    "created_at": law.created_at,
                    "processo": law.cnj,
                    "classe": law.class_type,
                    "assunto": law.subject,
                    "foro": law.comarca,
                    "vara": law.court,
                    "juiz": law.judge,
                    "endereco_forum": law.forum_address,
                    "status": law.status,
                    "data_distribuicao": law.distribution_date,
                    "data_ultima_movimentacao": law.last_movement_date,
                    "partes": parties_data or [],
                    "movimentacoes": law.movements
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
        raw_process = item.get("processo") or item.get("numero_processo")
        process_key = re.sub(r"\D", "", str(raw_process or ""))
        if process_key:
            return f"judicial:{process_key}"
        
        # If no process number, use id if it came from Lawsuit (which is unique per item), 
        # but since we can't easily distinguish Lawsuit ID from SearchResult ID here,
        # we fallback to content-based deduplication
        title = (item.get("title") or "").strip().lower()
        source = (item.get("source") or "").strip().lower()
        snippet = (item.get("snippet") or item.get("assunto") or "").strip().lower()
        
        # If even content is missing, use a random UUID so we don't deduplicate falsely
        if not title and not snippet:
            import uuid
            return f"judicial:uuid:{uuid.uuid4()}"
            
        return f"judicial:{title}|{source}|{snippet}"

    unique_results = []
    seen = set()
    for item in results:
        key = build_dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(item)
    
    return unique_results[offset:page_end]

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

STATE_TO_REGION = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul"
}

LOCAL_SOURCE_HINTS = [
    "diário", "diario", "gazeta", "tribuna", "folha", "jornal", "portal", "rádio", "radio",
    "tv", "prefeitura", "regional", "interior", "cidade", "municipal"
]

NATIONAL_SOURCE_HINTS = [
    "g1", "uol", "terra", "cnn", "globo", "estadão", "estadao", "folha de s", "veja", "r7", "band"
]

STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "para", "por", "com", "sem",
    "um", "uma", "uns", "umas", "a", "o", "as", "os", "sobre", "contra", "após", "apos", "entre"
}

def _safe_upper(value: str | None) -> str:
    return normalize_text(value or "").strip()

def _normalize_date_label(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "data não informada"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw[:19], fmt)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            continue
    return raw

def _to_state_code(item: dict) -> str:
    state = str(item.get("state") or "").upper().strip()
    if len(state) == 2 and state in STATE_TO_REGION:
        return state
    source = str(item.get("source") or "").split("+")[0].strip().upper()
    if len(source) == 2 and source in STATE_TO_REGION:
        return source
    mapped = TRIBUNAL_TO_STATE.get(source)
    if mapped in STATE_TO_REGION:
        return mapped
    return "NA"

def _classify_source_scope(source: str) -> str:
    normalized = _safe_upper(source)
    if any(_safe_upper(hint) in normalized for hint in NATIONAL_SOURCE_HINTS):
        return "nacional"
    if any(_safe_upper(hint) in normalized for hint in LOCAL_SOURCE_HINTS):
        return "local"
    return "regional"

def _extract_focus_topic(text: str) -> str:
    normalized = _safe_upper(text)
    topic_map = {
        "exploração sexual": ["EXPLORACAO SEXUAL", "TRAFICO SEXUAL", "TRAFICO DE PESSOAS"],
        "abuso sexual infantil": ["ABUSO SEXUAL INFANTIL", "ABUSO INFANTIL", "PORNOGRAFIA INFANTIL"],
        "violência sexual contra vulneráveis": ["ESTUPRO DE VULNERAVEL", "ABUSO SEXUAL DE INCAPAZ", "VIOLENCIA SEXUAL"],
        "aliciamento e crimes digitais": ["ALICIAMENTO", "INTERNET", "PREDADOR SEXUAL", "PEDOFILIA"]
    }
    for topic, tokens in topic_map.items():
        if any(token in normalized for token in tokens):
            return topic
    return "crimes sexuais e violência contra vulneráveis"

def _extract_who(title: str) -> str:
    cleaned = (title or "").strip()
    if not cleaned:
        return "agentes citados pela imprensa"
    for sep in [":", "-", "—", "|"]:
        if sep in cleaned:
            candidate = cleaned.split(sep, 1)[0].strip()
            if len(candidate) >= 4:
                return candidate
    return cleaned[:90]

def _extract_what(snippet: str, title: str) -> str:
    base = (snippet or "").strip() or (title or "").strip()
    if not base:
        return "fato sem detalhamento textual na fonte indexada"
    sentence = re.split(r"[.!?]", base, maxsplit=1)[0].strip()
    return sentence[:180]

def _extract_modus(text: str) -> str:
    normalized = _safe_upper(text)
    modus_map = [
        ("aliciamento digital", ["INTERNET", "REDE SOCIAL", "APLICATIVO", "MENSAGEM"]),
        ("abordagem presencial de vulneráveis", ["ABORDOU", "EM FLAGRANTE", "EM RESIDENCIA", "EM ESCOLA"]),
        ("rede de exploração com múltiplos envolvidos", ["OPERACAO", "QUADRILHA", "ASSOCIACAO", "GRUPO"]),
        ("produção ou compartilhamento de material ilícito", ["PORNOGRAFIA", "ARQUIVO", "FOTO", "VIDEO"])
    ]
    for label, tokens in modus_map:
        if any(token in normalized for token in tokens):
            return label
    return "modus operandi não explicitado de forma objetiva pela reportagem"

def _event_signature(item: dict) -> str:
    title = _safe_upper(item.get("title") or "")
    city = _safe_upper(item.get("city") or "DESCONHECIDO")
    state = _safe_upper(item.get("state") or "BR")
    tokens = [token for token in re.findall(r"[A-Z0-9]+", title) if token.lower() not in STOPWORDS and len(token) > 2]
    base = " ".join(tokens[:7])
    return f"{state}|{city}|{base}"

def _build_storytelling(news_items: list[dict], term: str | None) -> tuple[str, list[dict]]:
    deduped = []
    seen = set()
    for item in news_items:
        key = normalize_url(item.get("url") or "")
        if not key:
            key = f"{_safe_upper(item.get('title'))}|{_safe_upper(item.get('source'))}|{_safe_upper(item.get('published_date'))}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    if not deduped:
        empty_story = (
            "### Storytelling Jornalístico-Analítico\n\n"
            "Na janela de consulta atual, a imprensa não apresentou volume suficiente de reportagens públicas para compor uma narrativa factual robusta. "
            "Mesmo assim, a leitura mantém foco em evidências jornalísticas verificáveis e evita inferências não sustentadas.\n\n"
            "#### Apresentação\n"
            "O tema analisado permanece em monitoramento, aguardando novas publicações em veículos nacionais e locais.\n\n"
            "#### Desenvolvimento dos Fatos\n"
            "Sem amostra jornalística consistente nesta consulta, não há base para descrever escalada territorial ou sequência de eventos com segurança analítica.\n\n"
            "#### Conclusão\n"
            "O panorama midiático atual é de baixa densidade informacional para o recorte solicitado."
        )
        return empty_story, []

    grouped = defaultdict(list)
    for item in deduped:
        grouped[_event_signature(item)].append(item)

    ordered_groups = sorted(grouped.values(), key=len, reverse=True)
    local_count = 0
    national_count = 0
    sources = set()
    states = set()
    cities = set()
    facts = []

    for group in ordered_groups:
        pivot = group[0]
        source = str(pivot.get("source") or "imprensa não identificada")
        scope = _classify_source_scope(source)
        if scope == "local":
            local_count += 1
        if scope == "nacional":
            national_count += 1

        city = str(pivot.get("city") or "não informado")
        state = str(pivot.get("state") or "BR")
        states.add(state)
        cities.add(city)
        sources.add(source)

        title = str(pivot.get("title") or "")
        snippet = str(pivot.get("snippet") or "")
        text = f"{title} {snippet}"
        facts.append({
            "who": _extract_who(title),
            "what": _extract_what(snippet, title),
            "when": _normalize_date_label(pivot.get("published_date") or pivot.get("created_at")),
            "where": f"{city}/{state}",
            "modus": _extract_modus(text),
            "source": source,
            "scope": scope,
            "reports_count": len(group)
        })

    main_topic = _extract_focus_topic(term or " ".join([str(item.get("title") or "") for item in deduped[:20]]))
    top_sources = ", ".join(sorted(list(sources))[:4]) or "fontes jornalísticas diversas"
    top_groups = facts[:4]

    story_parts = [
        "### Storytelling Jornalístico-Analítico",
        "",
        "#### Apresentação",
        f"O caso em evidência, segundo a cobertura da imprensa, gira em torno de **{main_topic}**. "
        f"Conforme reportado por veículos de circulação nacional e por jornais regionais, a narrativa reúne {len(deduped)} reportagens úteis, "
        f"com ocorrências em {len(states)} estados e {len(cities)} cidades. As menções mais recorrentes aparecem em {top_sources}.",
        "",
        "#### Desenvolvimento dos Fatos",
    ]

    for idx, fact in enumerate(top_groups, start=1):
        source_phrase = "imprensa local" if fact["scope"] == "local" else ("grandes jornais de circulação nacional" if fact["scope"] == "nacional" else "veículos regionais")
        multiplicity = f" (com {fact['reports_count']} reportagens convergentes)" if fact["reports_count"] > 1 else ""
        story_parts.append(
            f"{idx}. Segundo {source_phrase}, em {fact['when']}, **{fact['who']}** foi citado em contexto de {fact['what']}{multiplicity}. "
            f"O ponto geográfico associado é {fact['where']}, e o suposto modus operandi descrito publicamente indica {fact['modus']}."
        )

    story_parts.extend([
        "",
        "#### Conclusão",
        f"O panorama midiático atual mostra combinação de cobertura nacional ({national_count} núcleos de eventos) e capilaridade local ({local_count} núcleos), "
        "o que sugere continuidade temática entre municípios e possível repetição de padrões noticiados. "
        "A leitura permanece estritamente factual e baseada no que foi publicado em fontes abertas."
    ])

    return "\n".join(story_parts), facts

def _build_judicial_bi(lawsuits: list[dict]) -> dict:
    total_national = len(lawsuits)
    known_total = 0
    state_counts = Counter()
    city_counts = Counter()
    region_counts = Counter()
    unknown_state_cases = 0

    for law in lawsuits:
        state = _to_state_code(law)
        city = str(law.get("city") or "DESCONHECIDO").strip().upper() or "DESCONHECIDO"
        if state in STATE_TO_REGION:
            state_counts[state] += 1
            city_counts[(city, state)] += 1
            region = STATE_TO_REGION.get(state, "Não classificado")
            region_counts[region] += 1
            known_total += 1
        else:
            unknown_state_cases += 1

    regional_distribution = []
    for region, count in region_counts.most_common():
        pct = (count / known_total * 100) if known_total else 0
        regional_distribution.append({"region": region, "count": count, "percent": round(pct, 2)})

    state_ranking = [{"state": state, "count": count} for state, count in state_counts.most_common(10)]
    municipal_focus = [{"city": city, "state": state, "count": count} for (city, state), count in city_counts.most_common(10)]

    return {
        "total_national": total_national,
        "known_state_total": known_total,
        "unknown_state_cases": unknown_state_cases,
        "regional_distribution": regional_distribution,
        "state_ranking": state_ranking,
        "municipal_focus": municipal_focus
    }

def _build_news_bi(news_items: list[dict]) -> dict:
    total_national = len(news_items)
    known_total = 0
    state_counts = Counter()
    city_counts = Counter()
    region_counts = Counter()
    unknown_state_cases = 0

    for item in news_items:
        state = str(item.get("state") or "NA").strip().upper()
        city = str(item.get("city") or "DESCONHECIDO").strip().upper() or "DESCONHECIDO"
        if state in STATE_TO_REGION:
            state_counts[state] += 1
            city_counts[(city, state)] += 1
            region_counts[STATE_TO_REGION[state]] += 1
            known_total += 1
        else:
            unknown_state_cases += 1

    regional_distribution = []
    for region, count in region_counts.most_common():
        pct = (count / known_total * 100) if known_total else 0
        regional_distribution.append({"region": region, "count": count, "percent": round(pct, 2)})

    state_ranking = [{"state": state, "count": count} for state, count in state_counts.most_common(10)]
    municipal_focus = [{"city": city, "state": state, "count": count} for (city, state), count in city_counts.most_common(10)]
    return {
        "total_national": total_national,
        "known_state_total": known_total,
        "unknown_state_cases": unknown_state_cases,
        "regional_distribution": regional_distribution,
        "state_ranking": state_ranking,
        "municipal_focus": municipal_focus
    }

def _format_bi_markdown(bi: dict) -> str:
    lines = ["### Panorama Estatístico (BI)", ""]
    lines.append("#### Nível Nacional")
    lines.append(f"- Total de registros identificados: **{bi.get('total_national', 0)}**")
    lines.append("")
    lines.append("#### Nível Regional")
    regional = bi.get("regional_distribution", [])
    if regional:
        for item in regional:
            lines.append(f"- **{item['region']}**: {item['count']} registros ({item['percent']}%)")
    else:
        lines.append("- Dados insuficientes para distribuição regional.")
    lines.append("")
    lines.append("#### Nível Estadual")
    state_ranking = bi.get("state_ranking", [])
    if state_ranking:
        for item in state_ranking[:5]:
            lines.append(f"- **{item['state']}**: {item['count']} registros")
    else:
        lines.append("- Sem volume estadual consolidado no recorte atual.")
    lines.append("")
    lines.append("#### Nível Municipal")
    municipal_focus = bi.get("municipal_focus", [])
    if municipal_focus:
        for item in municipal_focus[:8]:
            lines.append(f"- **{item['city']}/{item['state']}**: {item['count']} registros")
    else:
        lines.append("- Sem focos municipais suficientes para ranqueamento.")
    return "\n".join(lines)

@router.get("/analyze")
def analyze_data(
    city: str = None,
    state: str = None,
    term: str = None,
    db: Session = Depends(get_db)
):
    news_items = list_catalog(
        city=city,
        state=state,
        term=term,
        source_type="news",
        limit=400,
        page=1,
        db=db
    )
    lawsuits = list_catalog(
        city=city,
        state=state,
        term=term,
        source_type="judicial",
        limit=5000,
        page=1,
        db=db
    )
    storytelling, facts = _build_storytelling(news_items=news_items, term=term)
    bi = _build_judicial_bi(lawsuits=lawsuits) if lawsuits else _build_news_bi(news_items=news_items)
    bi_markdown = _format_bi_markdown(bi)
    analysis_text = f"{storytelling}\n\n{bi_markdown}"

    return {
        "status": "success",
        "total_news": len(news_items),
        "total_lawsuits": len(lawsuits),
        "analysis": analysis_text,
        "storytelling": storytelling,
        "judicial_bi": bi,
        "news_facts": facts
    }
