from fastapi import APIRouter, HTTPException, Depends
from app.rpa.tjsp import TJSPRPA
from app.rpa.tjmt import TJMTRPA
from app.rpa.google_news import GoogleNewsRPA
from app.rpa.google_web import GoogleWebRPA
from app.core.supabase import get_supabase
from typing import Any
from app.api.endpoints.stats import TRIBUNAL_TO_STATE, COORDS, CNJ_CODE_MAP
import json
import unicodedata
import re
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

def search_local_db(query: str, client: Any) -> dict:
    """
    Busca na base local (Supabase News e SearchResult) antes de ir para externo.
    """
    local_results = {"results": [], "news": []}
    
    # 1. Buscar em News
    # PostgREST filter: title.ilike.%query%,snippet.ilike.%query%
    try:
        or_filter = f"title.ilike.%{query}%,snippet.ilike.%{query}%,url.ilike.%{query}%"
        response = client.table("news").select("*").or_(or_filter).execute()
        news_items = response.data
        
        for n in news_items:
            local_results["news"].append({
                "title": n.get("title"),
                "url": n.get("url"),
                "source": n.get("source"),
                "snippet": n.get("snippet"),
                "published_date": n.get("published_date"),
                "image_url": n.get("image_url"),
                "city": n.get("city"),
                "state": n.get("state"),
                "origin": "local_db"
            })
    except Exception as e:
        print(f"Error searching news in Supabase: {e}")

    # 2. Buscar em SearchResult (conteúdo JSON)
    # Supabase/Postgres JSON filtering is tricky via simple client if not indexed properly for text search.
    # We can try a simple text search on the JSON column cast to text, but postgrest doesn't support casting easily in filter.
    # However, we can fetch recent search results and filter in python for now, or use RPC if we had one.
    # Given the MVP constraint, let's fetch the last 50 SearchResults and filter in memory.
    try:
        response = client.table("search_result").select("*").order("created_at", desc=True).limit(50).execute()
        search_results = response.data

        seen_ids = set()
        
        for sr in search_results:
            content = sr.get("content")
            if not content or "results" not in content:
                continue
                
            for item in content["results"]:
                item_str = json.dumps(item).upper()
                if query.upper() in item_str:
                    unique_id = item.get("processo") or item.get("numero_processo") or item.get("id") or str(hash(item_str))
                    
                    # CORREÇÃO DE INTEGRIDADE: Validar Tribunal pelo CNJ
                    cnj_clean = re.sub(r"\D", "", str(unique_id))
                    if len(cnj_clean) == 20:
                        tr_id = cnj_clean[14:16]
                        correct_tribunal = CNJ_CODE_MAP.get(tr_id)
                        if correct_tribunal:
                            item["tribunal"] = correct_tribunal
                    
                    if unique_id not in seen_ids:
                        item["origin"] = "local_db"
                        local_results["results"].append(item)
                        seen_ids.add(unique_id)
    except Exception as e:
        print(f"Error searching results in Supabase: {e}")

    return local_results

@router.get("/")
def search_process(query: str, client: Any = Depends(get_supabase)):
    """
    Inicia uma consulta assistida.
    Prioriza base local (Supabase), depois tenta externo se possível.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 0. Busca Local Primeiro
    local_data = search_local_db(query, client)
    
    # Identificar Tribunal pelo CNJ
    tribunal_name = "TJSP" # Default
    rpa_instance = None
    
    cnj_match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.(\d{2})\.\d{4}", query)
    
    if cnj_match:
        tr_id = cnj_match.group(1)
        tribunal_name = CNJ_CODE_MAP.get(tr_id, f"TJ{tr_id}")
        
        if tr_id == "11": # MT
            rpa_instance = TJMTRPA()
        elif tr_id == "26": # SP
            rpa_instance = TJSPRPA()
        else:
            rpa_instance = None
            print(f"Tribunal {tribunal_name} (ID {tr_id}) não possui RPA implementado. Retornando apenas dados locais.")
    else:
        if "8.11" in query:
            tribunal_name = "TJMT"
            rpa_instance = TJMTRPA()
        else:
            tribunal_name = "TJSP"
            rpa_instance = TJSPRPA()

    # Registrar a busca no Supabase
    try:
        search_record_data = {
            "query": query, 
            "tribunal": f"{tribunal_name}+News",
            "created_at": datetime.now().isoformat()
        }
        res = client.table("search").insert(search_record_data).execute()
        search_record_id = res.data[0]['id'] if res.data else None
    except Exception as e:
        print(f"Error saving search record: {e}")
        search_record_id = None

    # 1. Executar RPA Tribunal
    rpa_result = {"results": [], "status": "skipped"}
    
    if rpa_instance:
        try:
            rpa_result = rpa_instance.search(query)
            filtered_results = []
            for item in rpa_result.get("results", []):
                text = f"{item.get('classe', '')} {item.get('assunto', '')} {item.get('descricao', '')} {item.get('raw', '')}"
                if is_relevant_content(text):
                    if cnj_match:
                         tr_id_res = cnj_match.group(1)
                         correct_tribunal_res = CNJ_CODE_MAP.get(tr_id_res)
                         if correct_tribunal_res:
                            item["tribunal"] = correct_tribunal_res
                    filtered_results.append(item)
            rpa_result["results"] = filtered_results

            # Salvar novos resultados no Supabase
            if filtered_results and search_record_id:
                client.table("search_result").insert({
                    "search_id": search_record_id,
                    "content": rpa_result,
                    "created_at": datetime.now().isoformat()
                }).execute()

        except Exception as e:
            print(f"Erro {tribunal_name}: {e}")
            rpa_result = {"status": "error", "error": str(e), "results": []}
    else:
        rpa_result["msg"] = f"Tribunal {tribunal_name} não suportado para busca externa automática. Exibindo registros locais."

    # 2. Executar RPA Web
    web_rpa = GoogleWebRPA()
    web_result = {"results": [], "status": "skipped"}
    try:
        web_result = web_rpa.search(query)
        filtered_web = []
        for item in web_result.get("results", []):
            text = f"{item.get('classe', '')} {item.get('assunto', '')} {item.get('descricao', '')}"
            if is_relevant_content(text):
                if cnj_match:
                    tr_id_res = cnj_match.group(1)
                    correct_tribunal_res = CNJ_CODE_MAP.get(tr_id_res)
                    if correct_tribunal_res:
                        item["tribunal"] = correct_tribunal_res
                filtered_web.append(item)
        web_result["results"] = filtered_web

        if filtered_web and search_record_id:
             client.table("search_result").insert({
                "search_id": search_record_id,
                "content": web_result,
                "created_at": datetime.now().isoformat()
             }).execute()
    except Exception as e:
        print(f"Erro Web: {e}")
        web_result = {"status": "error", "error": str(e), "results": []}

    # 3. Executar RPA Google News
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

        if news_result.get("status") == "success" and search_record_id:
            for item in news_result.get("results", []):
                # Check duplication using URL
                exists = client.table("news").select("id").eq("url", item["url"]).execute()
                if not exists.data:
                    client.table("news").insert({
                        "search_id": search_record_id,
                        "title": item["title"],
                        "url": item["url"],
                        "source": item["source"],
                        "snippet": item["snippet"],
                        "image_url": item["image_url"],
                        "published_date": item.get("published_date"),
                        "city": item.get("city"),
                        "state": item.get("state"),
                        "created_at": datetime.now().isoformat()
                    }).execute()

    except Exception as e:
        print(f"Erro News: {e}")
        news_result = {"status": "error", "error": str(e), "results": []}

    # Combinar resposta
    final_judicial = local_data["results"]
    
    local_ids = {str(x.get("processo") or x.get("numero_processo")) for x in final_judicial}
    
    for item in rpa_result.get("results", []):
        pid = str(item.get("processo") or item.get("numero_processo"))
        if pid not in local_ids:
            final_judicial.append(item)
            if pid:
                local_ids.add(pid)
    
    for item in web_result.get("results", []):
        pid = str(item.get("processo") or item.get("numero_processo"))
        if not pid or pid not in local_ids:
            final_judicial.append(item)
            if pid:
                local_ids.add(pid)
            
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

@router.delete("/clean")
def clean_duplicates(client: Any = Depends(get_supabase)):
    """
    Remove notícias duplicadas baseadas na URL (Implementação simplificada para Supabase).
    Supabase não suporta delete com subquery complexa facilmente via cliente simples.
    Vamos fazer em memória ou via SQL direto se possível (mas não temos raw sql access).
    """
    # Esta operação é custosa via API. Melhor evitar ou fazer em batches pequenos.
    # Vamos pular por enquanto ou implementar apenas um warning.
    return {"message": "Operação não suportada via API direta para grandes volumes. Use SQL Editor no Supabase."}

import logging
logger = logging.getLogger("uvicorn.error")

@router.post("/scan")
def news_deep_scan(client: Any = Depends(get_supabase)):
    """
    Realiza uma varredura massiva.
    """
    initial_count = client.table("news").select("id", count="exact").execute().count
    logger.info(f"Initial News Count: {initial_count}")
    
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
            # Busca profunda
            result = rpa.search(query, max_pages=10)
            
            if result.get("status") == "success":
                results_list = result.get("results", [])
                filtered_results = []
                for item in results_list:
                    text = f"{item.get('title', '')} {item.get('snippet', '')}"
                    if is_relevant_content(text):
                        filtered_results.append(item)
                
                # Criar registro de busca "sistema"
                try:
                    res = client.table("search").insert({
                        "query": query, 
                        "tribunal": "GoogleNewsDeepScan",
                        "created_at": datetime.now().isoformat()
                    }).execute()
                    search_record_id = res.data[0]['id']
                except:
                    search_record_id = None
                    continue
                
                batch_data = []
                seen_urls = set()
                
                for item in filtered_results:
                    url = item["url"]
                    if url in seen_urls:
                        continue
                        
                    # Check duplicata no banco (um a um é lento, mas seguro)
                    # Otimização: Pegar todas as URLs existentes que dão match com as URLs do batch?
                    # Melhor: Tentar inserir e ignorar erro de unique constraint se possível (upsert)
                    
                    batch_data.append({
                        "search_id": search_record_id,
                        "title": item["title"],
                        "url": url,
                        "source": item["source"],
                        "snippet": item["snippet"],
                        "image_url": item["image_url"],
                        "published_date": item.get("published_date"),
                        "city": item.get("city"),
                        "state": item.get("state"),
                        "created_at": datetime.now().isoformat()
                    })
                    seen_urls.add(url)
                    total_found += 1
                
                if batch_data:
                    # Upsert usando URL como chave única
                    try:
                        client.table("news").upsert(batch_data, on_conflict="url").execute()
                    except Exception as e:
                        logger.error(f"Error inserting batch: {e}")
                
        except Exception as e:
            logger.error(f"CRITICAL ERROR in scan loop: {e}")
            continue
            
    return {"status": "completed", "new_records": total_found}

@router.get("/catalog")
def list_catalog(
    city: str = None,
    state: str = None,
    term: str = None,
    source_type: str = "all",
    type: str = None,
    limit: int = 100,
    client: Any = Depends(get_supabase)
):
    """
    Retorna o catálogo unificado (Notícias + Processos) com filtros.
    """
    final_source_type = source_type
    if type and type != "all":
        final_source_type = type
        
    results = []
    
    # 1. Buscar Notícias
    if final_source_type in ["all", "news"]:
        query = client.table("news").select("*").order("created_at", desc=True).limit(limit * 5)
        
        if city:
            query = query.ilike("city", f"%{city}%")
        if state:
            query = query.ilike("state", f"%{state}%")
        
        # Filtro de termo (mais complexo via API, fazemos em memória se necessário ou usando OR simples)
        # O ideal é usar Full Text Search do Postgres, mas via API simples:
        if term:
            terms = parse_terms(term)
            if terms:
                # Construir filtro OR: title.ilike.%t1%,snippet.ilike.%t1%,...
                # Isso pode ficar grande. Vamos simplificar filtrando o primeiro termo na query e resto em memória
                t1 = terms[0]
                query = query.or_(f"title.ilike.%{t1}%,snippet.ilike.%{t1}%")

        try:
            resp = query.execute()
            news_items = resp.data
            
            for n in news_items:
                if not is_relevant_content(f"{n.get('title')} {n.get('snippet')}"):
                    continue
                
                # Refinar filtros em memória se houver múltiplos termos
                if term:
                    full_text = f"{n.get('title')} {n.get('snippet')}"
                    terms = parse_terms(term)
                    if not any(t.upper() in full_text.upper() for t in terms):
                        continue

                results.append({
                    "type": "news",
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "snippet": n.get("snippet"),
                    "source": n.get("source"),
                    "url": n.get("url"),
                    "image_url": n.get("image_url"),
                    "published_date": n.get("published_date"),
                    "city": n.get("city"),
                    "state": n.get("state"),
                    "created_at": n.get("created_at")
                })
        except Exception as e:
            print(f"Error fetching catalog news: {e}")

    # 2. Buscar Processos Judiciais
    if final_source_type in ["all", "judicial"]:
        # Join é complexo via API client simples. Vamos buscar SearchResults recentes.
        try:
            resp = client.table("search_result").select("*, search(tribunal)").order("created_at", desc=True).limit(limit * 5).execute()
            judicial_items = resp.data
            
            count = 0
            for row in judicial_items:
                if count >= limit: break
                
                data = row.get("content")
                if not data or "results" not in data: continue
                
                # Tribunal info comes from nested search object if available
                tribunal_info = row.get("search", {}).get("tribunal", "") if row.get("search") else ""
                
                base_state = "BR"
                if tribunal_info:
                    clean_tribunal = tribunal_info.split('+')[0].strip().upper()
                    base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "BR")

                for item in data["results"]:
                    if count >= limit: break

                    desc = item.get("descricao", "")
                    assunto = item.get("assunto", "")
                    full_text = f"{desc} {assunto} {item.get('classe', '')}"
                    
                    if term:
                        terms = parse_terms(term)
                        if not any(t.upper() in full_text.upper() for t in terms):
                            continue
                            
                    if not is_relevant_content(full_text):
                        continue

                    # Determinar Localização
                    final_city = "DESCONHECIDO"
                    final_state = base_state
                    
                    item_city = item.get("city")
                    if item_city:
                        final_city = item_city.upper()
                    else:
                        cidades_conhecidas = [k for k in COORDS.keys() if k != "DESCONHECIDO"]
                        for c in cidades_conhecidas:
                            if f" {c}" in f" {desc.upper()} " or f"DE {c}" in desc.upper():
                                final_city = c
                                break
                    
                    if item.get("state"):
                        final_state = item.get("state").upper()

                    if city and city.upper() not in final_city: continue
                    if state and state.upper() != final_state: continue

                    results.append({
                        "type": "judicial",
                        "id": row.get("id"),
                        "title": item.get("classe", "Processo Judicial"),
                        "snippet": desc or assunto,
                        "source": tribunal_info or "TRIBUNAL",
                        "url": None,
                        "image_url": None,
                        "published_date": item.get("data_distribuicao"),
                        "city": final_city,
                        "state": final_state,
                        "created_at": row.get("created_at"),
                        "processo": item.get("processo"),
                        "classe": item.get("classe"),
                        "assunto": item.get("assunto"),
                        "foro": item.get("foro"),
                        "vara": item.get("vara"),
                        "partes": item.get("partes", [])
                    })
                    count += 1
        except Exception as e:
            print(f"Error fetching catalog judicial: {e}")

    results.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return results[:limit]
