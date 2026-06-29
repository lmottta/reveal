from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import SessionLocal
from app.models.search import SearchResult, News, Search
from app.models.lawsuit import Lawsuit
import json
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

CITY_CACHE = {}

@router.get("/kpi")
def get_kpi_stats(term: str = None, limit: int = 5, db: Session = Depends(get_db)):
    """
    Retorna KPIs de ocorrências por cidade e estado.
    """
    city_counts = {}
    state_counts = {}
    state_judicial_counts = {}
    
    # Novos KPIs
    total_judicial = 0
    resolved_count = 0
    tramitacao_days = []
    competencia_counts = {}

    # 0. Processar Lawsuit (Base populada por RPA em massa)
    lawsuits_query = db.query(Lawsuit).limit(5000)
    
    # Filtro básico de query para Lawsuit (se possível)
    if term:
        terms = parse_terms(term)
        # Filtro em memória ou query complexa? 
        # Vamos filtrar em memória para manter consistência com a lógica abaixo
        pass 

    lawsuits = lawsuits_query.all()

    for law in lawsuits:
        # Construir texto de busca
        parties_txt = str(law.parties) if law.parties else ""
        search_text = f"{law.cnj} {law.judge} {law.court} {law.class_type} {law.subject} {parties_txt}"
        
        if term:
            terms = parse_terms(term)
            if not any(t.upper() in search_text.upper() for t in terms):
                continue
                
        if not is_relevant_content(search_text):
            continue
        
        # Mapeamento de Estado
        tribunal_clean = str(law.tribunal).split('+')[0].strip().upper()
        
        # Se já for sigla de estado (ex: SP, RJ), usa direto. Senão, tenta mapear (ex: TJSP -> SP)
        if len(tribunal_clean) == 2 and tribunal_clean in STATE_COORDS:
             state = tribunal_clean
        else:
             state = TRIBUNAL_TO_STATE.get(tribunal_clean, "BR")

        # Mapeamento de Cidade (Tentativa simples baseada na Vara/Comarca)
        city = "DESCONHECIDO"
        if law.court:
            parts = str(law.court).upper().split(" DE ")
            if len(parts) > 1 and parts[-1].strip():
                city = parts[-1].strip()
            else:
                city = str(law.court).upper().strip()
        
        # Incrementar contadores
        total_judicial += 1
        
        # Resolução
        situacao = (law.status or "").upper()
        is_resolved = "ARQUIVADO" in situacao or "BAIXA" in situacao or "JULGADO" in situacao or "ENCERRADO" in situacao
        if is_resolved:
            resolved_count += 1
        
        # Tempo (Aproximado)
        try:
            if law.distribution_date:
                # Tentar formatos comuns
                dt_start = None
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"]:
                    try:
                        dt_start = datetime.strptime(law.distribution_date, fmt)
                        break
                    except: pass
                
                if dt_start:
                    dt_end = law.last_update.replace(tzinfo=None) if law.last_update else datetime.now()
                    days = (dt_end - dt_start).days
                    if days >= 0:
                        tramitacao_days.append(days)
        except: pass

        # Competência
        classe = (law.class_type or "OUTROS").upper()
        competencia_counts[classe] = competencia_counts.get(classe, 0) + 1

        display_state = state
        city_key = f"{city} - {display_state}"
        
        city_counts[city_key] = city_counts.get(city_key, 0) + 1
        state_counts[display_state] = state_counts.get(display_state, 0) + 1
        state_judicial_counts[display_state] = state_judicial_counts.get(display_state, 0) + 1


    # 1. Processar Processos Judiciais (SearchResult - Legado/Busca Manual)
    results = db.query(SearchResult, Search.tribunal).join(Search, SearchResult.search_id == Search.id).order_by(SearchResult.created_at.desc()).limit(5000).all()
    
    for row, tribunal in results:
        data = row.content
        if not data or not isinstance(data, dict):
            continue
            
        results_list = data.get("results", [])
        if not results_list:
            continue

        base_state = "BR"
        if tribunal:
            clean_tribunal = str(tribunal).split('+')[0].strip().upper()
            base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "BR")

        for item in results_list:
            if not isinstance(item, dict):
                continue
            
            # Filtro de termo e relevância
            search_text = f"{item.get('descricao', '')} {item.get('assunto', '')} {item.get('classe', '')}"
            if term:
                terms = parse_terms(term)
                if not any(t.upper() in search_text.upper() for t in terms):
                    continue
            if not is_relevant_content(search_text):
                continue

            # --- LÓGICA DE KPI ---
            total_judicial += 1
            
            # 1. Resolução
            situacao = (item.get("situacao") or "").upper()
            movs = item.get("movimentacoes", [])
            last_mov = movs[0].get("conteudo", "").upper() if movs else ""
            
            is_resolved = "ARQUIVA" in situacao or "BAIXA" in situacao or "EXTINTO" in situacao or "JULGADO" in situacao
            if not is_resolved and last_mov:
                 is_resolved = "ARQUIVA" in last_mov or "BAIXA" in last_mov or "SENTENÇA" in last_mov

            if is_resolved:
                resolved_count += 1
            
            # 2. Tempo de Tramitação
            try:
                dt_dist = item.get("data_distribuicao")
                if dt_dist:
                    dt_start = datetime.strptime(dt_dist, "%d/%m/%Y")
                    # Tenta pegar data do último andamento ou usa hoje
                    last_date_str = item.get("ultimo_andamento", "").split(" - ")[0]
                    if last_date_str:
                         dt_end = datetime.strptime(last_date_str, "%d/%m/%Y")
                    else:
                         dt_end = datetime.now()
                    
                    days = (dt_end - dt_start).days
                    if days >= 0:
                        tramitacao_days.append(days)
            except:
                pass # Ignora erros de data
            
            # 3. Competência (Classe)
            classe = (item.get("classe") or "OUTROS").upper()
            # Normalização simples de classes comuns
            if "CRIMINAL" in classe or "PENAL" in classe: 
                if "EXECUÇÃO" in classe: classe = "EXECUÇÃO PENAL"
                elif "INQUÉRITO" in classe: classe = "INQUÉRITO POLICIAL"
                else: classe = "AÇÃO PENAL"
            elif "CÍVEL" in classe or "CIVEL" in classe: classe = "CÍVEL"
            elif "FAMÍLIA" in classe: classe = "FAMÍLIA"
            elif "INFÂNCIA" in classe: classe = "INFÂNCIA E JUVENTUDE"
            
            competencia_counts[classe] = competencia_counts.get(classe, 0) + 1

            # Normalização de Local
            city = (item.get("city") or "DESCONHECIDO").upper()
            state = (item.get("state") or base_state).upper()

            # Incrementa contadores
            display_city = city
            if city == "DESCONHECIDO":
                display_city = "DESCONHECIDO"
            
            display_state = state
            if state == "BR":
                display_state = "NACIONAL"

            city_key = f"{display_city} - {display_state}"
            city_counts[city_key] = city_counts.get(city_key, 0) + 1
            state_counts[display_state] = state_counts.get(display_state, 0) + 1
            state_judicial_counts[display_state] = state_judicial_counts.get(display_state, 0) + 1

    # 2. Processar Notícias
    news_query = db.query(News.city, News.state, News.title, News.snippet).order_by(News.created_at.desc()).limit(10000)
    news_items = news_query.all()

    for item in news_items:
        text = f"{item.title or ''} {item.snippet or ''}"
        if term:
            terms = parse_terms(term)
            if not any(t.upper() in text.upper() for t in terms):
                continue
        if not is_relevant_content(text):
            continue

        city = (item.city or "DESCONHECIDO").upper()
        state = (item.state or "BR").upper()
        
        display_city = city
        if city == "DESCONHECIDO":
            display_city = "DESCONHECIDO"
        
        display_state = state
        if state == "BR":
            display_state = "NACIONAL"

        city_key = f"{display_city} - {display_state}"
        city_counts[city_key] = city_counts.get(city_key, 0) + 1
        state_counts[display_state] = state_counts.get(display_state, 0) + 1

    # Formatar Resposta
    def get_top(data, limit):
        return [{"name": k, "value": v} for k, v in sorted(data.items(), key=lambda item: item[1], reverse=True)[:limit]]

    # --- CÁLCULOS FINAIS ---
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
def get_geo_stats(
    term: str = None,
    state: str = None,
    city: str = None,
    source_type: str = "judicial",
    max_news: int = 5000,
    max_judicial: int = 2000,
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas geográficas com filtro opcional por termo.
    """
    stats = {}
    state_filter = state.upper() if state else None
    city_filter = city.upper() if city else None

    if source_type in ["all", "judicial"]:
        lawsuits = db.query(Lawsuit).limit(5000).all()
        
        for law in lawsuits:
            parties_txt = str(law.parties) if law.parties else ""
            search_text = f"{law.cnj} {law.judge} {law.court} {law.class_type} {law.subject} {parties_txt}"
            
            if term:
                terms = parse_terms(term)
                if not any(t.upper() in search_text.upper() for t in terms):
                    continue
                    
            if not is_relevant_content(search_text):
                continue
            
            tribunal_clean = str(law.tribunal).split('+')[0].strip().upper()
            if len(tribunal_clean) == 2 and tribunal_clean in STATE_COORDS:
                 state = tribunal_clean
            else:
                 state = TRIBUNAL_TO_STATE.get(tribunal_clean, "NA")

            city = "DESCONHECIDO"
            if law.court:
                parts = str(law.court).upper().split(" DE ")
                if len(parts) > 1 and parts[-1].strip():
                    city = parts[-1].strip()
                else:
                    city = str(law.court).upper().strip()
            
            key = f"{city}|{state}"
            if state_filter and state != state_filter:
                continue
            if city_filter and city != city_filter:
                continue
            if key not in stats:
                stats[key] = {"city": city, "state": state, "count": 0, "type": "judicial"}
            stats[key]["count"] += 1

    if source_type in ["all", "judicial"]:
        if not max_judicial or max_judicial < 1:
            max_judicial = 2000
        if max_judicial > 20000:
            max_judicial = 20000
            
        results = db.query(SearchResult, Search.tribunal).join(Search, SearchResult.search_id == Search.id).order_by(SearchResult.created_at.desc()).limit(max_judicial).all()
        
        cidades_conhecidas = [k for k in COORDS.keys() if k != "DESCONHECIDO"]

        for row, search_obj in results:
            tribunal = search_obj

            data = row.content
            if not data or not isinstance(data, dict):
                 continue
            
            results_list = data.get("results", [])
            if not results_list:
                continue

            base_state = "NA"
            if tribunal:
                clean_tribunal = str(tribunal).split('+')[0].strip().upper()
                base_state = TRIBUNAL_TO_STATE.get(clean_tribunal, "NA")

            for item in results_list:
                if not isinstance(item, dict):
                    continue

                unique_id = item.get("processo") or item.get("numero_processo") or ""
                cnj_clean = re.sub(r"\D", "", unique_id)
                if len(cnj_clean) == 20:
                    tr_id = cnj_clean[14:16]
                    correct_tribunal = CNJ_CODE_MAP.get(tr_id)
                    if correct_tribunal:
                        item["tribunal"] = correct_tribunal
                        base_state = TRIBUNAL_TO_STATE.get(correct_tribunal, base_state)

                item_city = item.get("city")
                item_state = item.get("state")
                
                found_city = "DESCONHECIDO"
                found_state = base_state

                if item_city:
                    found_city = item_city.upper()
                
                if item_state:
                    found_state = item_state.upper()
                
                if found_city == "DESCONHECIDO":
                    desc = f"{item.get('descricao', '')} {item.get('foro', '')} {item.get('comarca', '')} {item.get('tribunal', '')}".upper()
                    
                    for city in cidades_conhecidas:
                        if f" {city}" in f" {desc} " or f"DE {city}" in desc or f"COMARCA DE {city}" in desc:
                            found_city = city
                            break
                
                search_text = f"{item.get('descricao', '')} {item.get('assunto', '')} {item.get('classe', '')} {found_city}"
                terms = parse_terms(term)
                if terms and not any(t.upper() in search_text.upper() for t in terms):
                    continue
                if not is_relevant_content(search_text):
                    continue

                key = f"{found_city}|{found_state}"
                if state_filter and found_state != state_filter:
                    continue
                if city_filter and found_city != city_filter:
                    continue
                
                if key not in stats:
                    stats[key] = {"city": found_city, "state": found_state, "count": 0, "type": "judicial"}
                else:
                    if stats[key]["type"] == "news":
                        stats[key]["type"] = "mixed"
                
                stats[key]["count"] += 1

    if source_type in ["all", "news"]:
        if not max_news or max_news < 1:
            max_news = 5000
        if max_news > 200000:
            max_news = 200000
        query = db.query(News.city, News.state, News.title, News.snippet).order_by(News.created_at.desc()).limit(max_news)
        news_items = query.all()

        for item in news_items:
            text = f"{item.title or ''} {item.snippet or ''}"
            terms = parse_terms(term)
            if terms and not any(t.upper() in text.upper() for t in terms):
                continue
            city = item.city.upper() if item.city else "DESCONHECIDO"
            state = item.state.upper() if item.state else "NA"

            key = f"{city}|{state}"
            if state_filter and state != state_filter:
                continue
            if city_filter and city != city_filter:
                continue
            if key not in stats:
                 stats[key] = {"city": city, "state": state, "count": 0, "type": "news"}
            elif stats[key]["type"] == "judicial":
                 stats[key]["type"] = "mixed"
            
            stats[key]["count"] += 1

    response = []
    for key, data in stats.items():
        city_name = data["city"]
        state_code = data["state"]
        
        coords = None

        # Prioridade 1: Coordenada exata da cidade
        if city_name != "DESCONHECIDO":
            coords = COORDS.get(city_name)
        
        # Prioridade 2: Fallback por Estado (Se cidade for DESCONHECIDO ou não achada)
        if not coords and state_code in STATE_COORDS:
            coords = STATE_COORDS[state_code]
            
        # Prioridade 3: Match parcial de nome de cidade
        if not coords and city_name != "DESCONHECIDO":
             for c_key, c_val in COORDS.items():
                if c_key == city_name or (len(city_name) > 3 and c_key.startswith(city_name)):
                    coords = c_val
                    break

        # Prioridade 4: Fallback Geral (Brasília)
        if not coords:
            coords = COORDS.get("DESCONHECIDO")

        if coords:
            response.append({
                "city": city_name,
                "state": state_code,
                "count": data["count"],
                "type": data["type"],
                "lat": coords["lat"],
                "lng": coords["lng"]
            })
        
    return response


@router.get("/ufs/{uf}/cities")
def list_cities_by_uf(uf: str):
    normalized = uf.upper()
    if normalized not in STATE_COORDS:
        return []
    cached = CITY_CACHE.get(normalized)
    if cached:
        return cached
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{normalized}/municipios?orderBy=nome"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return []
        data = res.json()
        cities = [item.get("nome", "").upper() for item in data if item.get("nome")]
        CITY_CACHE[normalized] = cities
        return cities
    except Exception:
        return []
