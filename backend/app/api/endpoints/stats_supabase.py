from fastapi import APIRouter, Depends
from app.core.supabase import get_supabase
from typing import Any
import requests
import unicodedata
import re
from datetime import datetime
from app.core.constants import (
    CNJ_CODE_MAP,
    RELEVANT_KEYWORDS,
    COORDS,
    STATE_COORDS,
    TRIBUNAL_TO_STATE
)

router = APIRouter()

def normalize_text(value: str) -> str:
    if not value: return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.upper()

def is_relevant_content(value: str) -> bool:
    text = normalize_text(value)
    return any(keyword in text for keyword in RELEVANT_KEYWORDS)

def parse_terms(raw: str | None) -> list[str]:
    if not raw: return []
    return [term.strip() for term in raw.replace(",", "|").split("|") if term.strip()]

CITY_CACHE = {}

@router.get("/kpi")
def get_kpi_stats(term: str = None, limit: int = 5, client: Any = Depends(get_supabase)):
    city_counts = {}
    state_counts = {}
    state_judicial_counts = {}
    
    total_judicial = 0
    resolved_count = 0
    tramitacao_days = []
    competencia_counts = {}

    try:
        resp = client.table("search_result").select("*, search(tribunal)").order("created_at", desc=True).limit(5000).execute()
        results = resp.data
        
        for row in results:
            data = row.get("content")
            if not data or not isinstance(data, dict):
                continue
            
            tribunal_info = ""
            search_relation = row.get("search")
            if search_relation and isinstance(search_relation, dict):
                tribunal_info = search_relation.get("tribunal", "")
            
            base_state = "BR"
            if tribunal_info:
                clean_tribunal = str(tribunal_info).split('+')[0].strip().upper()
                base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "BR")

            results_list = data.get("results", [])
            if not results_list: continue

            for item in results_list:
                if not isinstance(item, dict): continue
                
                search_text = f"{item.get('descricao', '')} {item.get('assunto', '')} {item.get('classe', '')}"
                if term:
                    terms = parse_terms(term)
                    if not any(t.upper() in search_text.upper() for t in terms):
                        continue
                if not is_relevant_content(search_text):
                    continue

                total_judicial += 1
                
                situacao = (item.get("situacao") or "").upper()
                movs = item.get("movimentacoes", [])
                last_mov = ""
                if movs and isinstance(movs, list) and len(movs) > 0:
                    last_mov = movs[0].get("conteudo", "").upper()
                
                is_resolved = "ARQUIVA" in situacao or "BAIXA" in situacao or "EXTINTO" in situacao or "JULGADO" in situacao
                if not is_resolved and last_mov:
                    is_resolved = "ARQUIVA" in last_mov or "BAIXA" in last_mov or "SENTENÇA" in last_mov
                
                if is_resolved: resolved_count += 1
                
                try:
                    dt_dist = item.get("data_distribuicao")
                    if dt_dist:
                        dt_start = datetime.strptime(dt_dist, "%d/%m/%Y")
                        last_date_str = ""
                        last_andamento = item.get("ultimo_andamento", "")
                        if last_andamento:
                            last_date_str = last_andamento.split(" - ")[0]
                        
                        if last_date_str:
                            dt_end = datetime.strptime(last_date_str, "%d/%m/%Y")
                        else:
                            dt_end = datetime.now()
                        
                        days = (dt_end - dt_start).days
                        if days >= 0: tramitacao_days.append(days)
                except: pass
                
                classe = (item.get("classe") or "OUTROS").upper()
                if "CRIMINAL" in classe or "PENAL" in classe: 
                    if "EXECUÇÃO" in classe: classe = "EXECUÇÃO PENAL"
                    elif "INQUÉRITO" in classe: classe = "INQUÉRITO POLICIAL"
                    else: classe = "AÇÃO PENAL"
                elif "CÍVEL" in classe or "CIVEL" in classe: classe = "CÍVEL"
                elif "FAMÍLIA" in classe: classe = "FAMÍLIA"
                elif "INFÂNCIA" in classe: classe = "INFÂNCIA E JUVENTUDE"
                
                competencia_counts[classe] = competencia_counts.get(classe, 0) + 1

                city = (item.get("city") or "DESCONHECIDO").upper()
                state = (item.get("state") or base_state).upper()
                
                display_city = "INDETERMINADO" if city == "DESCONHECIDO" else city
                display_state = "NACIONAL" if state == "BR" else state

                city_key = f"{display_city} - {display_state}"
                city_counts[city_key] = city_counts.get(city_key, 0) + 1
                state_counts[display_state] = state_counts.get(display_state, 0) + 1
                state_judicial_counts[display_state] = state_judicial_counts.get(display_state, 0) + 1
    except Exception as e:
        print(f"Error stats judicial: {e}")

    try:
        news_query = client.table("news").select("city, state, title, snippet").order("created_at", desc=True).limit(5000)
        resp = news_query.execute()
        news_items = resp.data
        
        for item in news_items:
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if term:
                terms = parse_terms(term)
                if not any(t.upper() in text.upper() for t in terms):
                    continue
            if not is_relevant_content(text):
                continue

            city = (item.get("city") or "DESCONHECIDO").upper()
            state = (item.get("state") or "BR").upper()
            
            display_city = "INDETERMINADO" if city == "DESCONHECIDO" else city
            display_state = "NACIONAL" if state == "BR" else state

            city_key = f"{display_city} - {display_state}"
            city_counts[city_key] = city_counts.get(city_key, 0) + 1
            state_counts[display_state] = state_counts.get(display_state, 0) + 1
    except Exception as e:
        print(f"Error stats news: {e}")

    def get_top(data, limit):
        return [{"name": k, "value": v} for k, v in sorted(data.items(), key=lambda item: item[1], reverse=True)[:limit]]

    taxa_resolucao = (resolved_count / total_judicial * 100) if total_judicial > 0 else 0
    tempo_medio = (sum(tramitacao_days) / len(tramitacao_days)) if tramitacao_days else 0
    top_competencias = [{"name": k, "value": v} for k, v in sorted(competencia_counts.items(), key=lambda item: item[1], reverse=True)[:5]]

    return {
        "top_cities_overall": get_top(city_counts, limit),
        "top_states_overall": get_top(state_counts, limit),
        "top_states_judicial": get_top(state_judicial_counts, limit),
        "kpi_resolucao": round(taxa_resolucao, 1),
        "kpi_tempo_medio": int(tempo_medio),
        "kpi_competencias": top_competencias
    }

@router.get("/geo")
def get_geo_stats(term: str = None, max_news: int = 5000, max_judicial: int = 2000, client: Any = Depends(get_supabase)):
    stats = {}
    
    try:
        resp = client.table("search_result").select("*, search(tribunal)").order("created_at", desc=True).limit(max_judicial).execute()
        results = resp.data
        
        cidades_conhecidas = [k for k in COORDS.keys() if k != "DESCONHECIDO"]

        for row in results:
            tribunal_info = ""
            search_relation = row.get("search")
            if search_relation and isinstance(search_relation, dict):
                tribunal_info = search_relation.get("tribunal", "")
                
            base_state = "BR"
            if tribunal_info:
                clean_tribunal = str(tribunal_info).split('+')[0].strip().upper()
                base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "BR")
                
            data = row.get("content")
            if not data or not isinstance(data, dict): continue
            
            results_list = data.get("results", [])
            for item in results_list:
                if not isinstance(item, dict): continue
                
                # CORREÇÃO DE INTEGRIDADE
                unique_id = str(item.get("processo") or item.get("numero_processo") or "")
                cnj_clean = re.sub(r"\D", "", unique_id)
                if len(cnj_clean) == 20:
                    tr_id = cnj_clean[14:16]
                    correct_tribunal = CNJ_CODE_MAP.get(tr_id)
                    if correct_tribunal:
                        item["tribunal"] = correct_tribunal
                        base_state = TRIBUNAL_TO_STATE.get(correct_tribunal, base_state)

                found_city = (item.get("city") or "DESCONHECIDO").upper()
                found_state = (item.get("state") or base_state).upper()
                
                if found_city == "DESCONHECIDO":
                    desc = f"{item.get('descricao', '')} {item.get('foro', '')} {item.get('comarca', '')} {item.get('tribunal', '')}".upper()
                    for c in cidades_conhecidas:
                        if f" {c}" in f" {desc} " or f"DE {c}" in desc:
                            found_city = c
                            break
                
                search_text = f"{item.get('descricao', '')} {item.get('assunto', '')} {item.get('classe', '')} {found_city}"
                if term:
                    terms = parse_terms(term)
                    if not any(t.upper() in search_text.upper() for t in terms): continue
                if not is_relevant_content(search_text): continue
                
                key = f"{found_city}|{found_state}"
                if key not in stats:
                    stats[key] = {"city": found_city, "state": found_state, "count": 0, "type": "judicial"}
                else:
                    if stats[key]["type"] == "news": stats[key]["type"] = "mixed"
                stats[key]["count"] += 1
    except Exception as e:
        print(f"Error geo judicial: {e}")

    try:
        query = client.table("news").select("city, state, title, snippet").order("created_at", desc=True).limit(max_news)
        resp = query.execute()
        for item in resp.data:
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            if term:
                terms = parse_terms(term)
                if not any(t.upper() in text.upper() for t in terms): continue
            if not is_relevant_content(text): continue
            
            city = (item.get("city") or "DESCONHECIDO").upper()
            state = (item.get("state") or "BR").upper()
            
            key = f"{city}|{state}"
            if key not in stats:
                stats[key] = {"city": city, "state": state, "count": 0, "type": "news"}
            elif stats[key]["type"] == "judicial":
                stats[key]["type"] = "mixed"
            stats[key]["count"] += 1
    except Exception as e:
        print(f"Error geo news: {e}")
        
    response = []
    for key, data in stats.items():
        city_name = data["city"]
        state_code = data["state"]
        coords = None
        
        if city_name != "DESCONHECIDO": coords = COORDS.get(city_name)
        if not coords and state_code in STATE_COORDS: coords = STATE_COORDS[state_code]
        if not coords and city_name != "DESCONHECIDO":
             for c_key, c_val in COORDS.items():
                if c_key == city_name or (len(city_name) > 3 and c_key.startswith(city_name)):
                    coords = c_val
                    break
        if not coords: coords = COORDS.get("DESCONHECIDO")
        
        if coords:
            response.append({
                "city": city_name, "state": state_code, "count": data["count"],
                "type": data["type"], "lat": coords["lat"], "lng": coords["lng"]
            })
    return response

@router.get("/ufs/{uf}/cities")
def list_cities_by_uf(uf: str):
    normalized = uf.upper()
    if normalized not in STATE_COORDS: return []
    if normalized in CITY_CACHE: return CITY_CACHE[normalized]
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{normalized}/municipios?orderBy=nome"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            cities = [item.get("nome", "").upper() for item in data if item.get("nome")]
            CITY_CACHE[normalized] = cities
            return cities
    except: pass
    return []
