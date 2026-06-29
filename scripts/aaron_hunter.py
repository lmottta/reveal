import sys
import os
import time
import random
import unicodedata
import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

from app.db.session import SessionLocal
from app.models.lawsuit import Target
from app.models.search import News
from app.rpa.google_news import GoogleNewsRPA

# Keywords focused EXCLUSIVELY on sexual violence and vulnerable protection
KEYWORDS = [
    "operação policial pedofilia",
    "preso por estupro de vulnerável",
    "acusado de importunação sexual",
    "rede de exploração sexual desmantelada",
    "condenado por abuso infantil",
    "aliciamento de menores internet preso",
    "trafico de pessoas exploração sexual",
    "mandado de prisão estupro de vulneravel",
    "predador sexual preso",
    "investigado por abuso",
    "réu por estupro",
    "preso em flagrante estupro"
]

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "GO", "DF", "PE", "CE"]

def normalize_text(value: str) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return normalized.upper().strip()

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

def extract_name(text: str) -> Optional[str]:
    """
    Extract potential target names from text using heuristics.
    """
    if not text:
        return None
        
    text_clean = text.replace("Policia Civil", "").replace("Policia Militar", "")
    text_clean = text_clean.replace("Delegacia", "").replace("Justiça", "")
    
    name_regex = r"([A-Z][a-zÀ-ÿ]+(?: (?:da|de|do|das|dos) )?(?: [A-Z][a-zÀ-ÿ]+)+)"
    
    patterns = [
        rf"(?:advogado|juiz|promotor|réu|acusada|acusado|vítima|suspeita|suspeito|presa|preso|condenada|condenado|denunciada|denunciado) (?:de )?{name_regex}",
        rf"{name_regex}, de \d{{1,2}} anos",
        rf"prisão de {name_regex}",
        rf"contra {name_regex}",
        rf"homem identificado como {name_regex}",
        rf"mulher identificada como {name_regex}",
        r"(Operação [A-Z][a-zÀ-ÿ]+(?: [A-Z][a-zÀ-ÿ]+)*)"
    ]
    
    blocklist = [
        "Policia", "Delegacia", "Justiça", "Tribunal", "Ministério", "Publico", "Defensoria",
        "Rio de Janeiro", "São Paulo", "Mato Grosso", "Minas Gerais", "Espirito Santo",
        "Santa Catarina", "Rio Grande", "Distrito Federal", "Governo", "Estado", "Uniao",
        "Civil", "Militar", "Federal", "Guarda", "Avenida", "Rua", "Praça", "Alameda",
        "Estrada", "Rodovia", "Via", "Largo", "Jardim", "Parque", "Vila", "Cidade", "Bairro", "Centro",
        "Bom Prato", "Blue Tree", "Smart Sampa", "Lei Seca", "Cabo Frio", "Zona Norte", "Zona Sul"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_clean)
        if match:
            name = match.group(1).strip()
            if len(name) > 5 and all(b.upper() not in name.upper() for b in blocklist):
                return name
            else:
                # Debug discarded name
                pass
    return None

def aaron_data_hunter():
    print("===============================================================")
    print("🦅 AARON DATA HUNTER - INICIANDO VARREDURA DE DADOS PÚBLICOS 🦅")
    print("Objetivo: Coleta de Alvos e Notícias (Crimes Sexuais/Vulneráveis)")
    print("===============================================================\n")

    db = SessionLocal()
    rpa = GoogleNewsRPA()
    
    total_news = 0
    total_targets = 0
    
    random.shuffle(STATES)
    random.shuffle(KEYWORDS)
    
    try:
        for state in STATES[:5]: # Limit to 5 random states per run to avoid huge execution times
            for keyword in KEYWORDS[:3]: # Limit to 3 random keywords per state
                query = f"{keyword} {state}"
                print(f"[*] Buscando: '{query}'...")
                
                try:
                    result_dict = rpa.search(query, max_pages=2)
                    
                    if result_dict.get("status") == "error":
                        print(f"  [!] Falha na busca: {result_dict.get('error')}")
                        continue
                        
                    items = result_dict.get("results", [])
                    print(f"  [+] Encontrados {len(items)} resultados brutos.")
                    
                    for item in items:
                        try:
                            # 1. Deduplicação Rigorosa de URL e Título
                            url = normalize_url(item.get("url"))
                            title_norm = normalize_text(item.get("title"))
                            
                            if not url or not title_norm:
                                continue
                                
                            existing_url = db.query(News).filter(News.url == url).first()
                            if existing_url:
                                continue
                                
                            # Verifica similaridade de título (para evitar a mesma notícia em sites diferentes)
                            # Buscamos títulos exatos (já normalizados no banco não temos, então buscamos por like)
                            existing_title = db.query(News).filter(News.title == item.get("title")).first()
                            if existing_title:
                                continue
                                
                            # 2. Salvar Notícia
                            news = News(
                                title=item.get("title"),
                                url=url,
                                source=item.get("source"),
                                snippet=item.get("snippet"),
                                published_date=item.get("published_date"),
                                image_url=item.get("image_url"),
                                city=item.get("city"),
                                state=item.get("state") or state
                            )
                            db.add(news)
                            db.commit()
                            total_news += 1
                            
                            # 3. Extrair e Salvar Alvo (Target)
                            name_from_title = extract_name(item.get("title"))
                            name_from_snippet = extract_name(item.get("snippet"))
                            target_name = name_from_title or name_from_snippet
                            
                            if target_name:
                                existing_target = db.query(Target).filter(Target.name == target_name).first()
                                if not existing_target:
                                    print(f"    [🎯] NOVO ALVO IDENTIFICADO: {target_name}")
                                    new_target = Target(
                                        name=target_name,
                                        source=f"News: {item.get('source')}"
                                    )
                                    db.add(new_target)
                                    db.commit()
                                    total_targets += 1
                                else:
                                    db.rollback()
                        except Exception as item_error:
                             db.rollback()
                             continue
                except Exception as e:
                    print(f"  [!] Erro no processamento de '{query}': {e}")
                    db.rollback()
                    continue
                
                time.sleep(random.uniform(2, 4))
                
    except KeyboardInterrupt:
        print("\n[!] Interrompido pelo usuário.")
    finally:
        db.close()
        print("\n===============================================================")
        print(f"📊 RESUMO DA OPERAÇÃO AARON HUNTER:")
        print(f"   Novas Notícias Desduplicadas: {total_news}")
        print(f"   Novos Alvos Identificados: {total_targets}")
        print("===============================================================\n")

if __name__ == "__main__":
    aaron_data_hunter()
