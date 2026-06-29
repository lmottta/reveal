import sys
import os
import re
import time
from typing import List, Optional

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

# Set python path for imports
sys.path.append(backend_dir)

from app.db.session import SessionLocal
from app.models.lawsuit import Target
from app.models.search import News
from app.rpa.google_news import GoogleNewsRPA

# Keywords focused EXCLUSIVELY on sexual violence and vulnerable protection
KEYWORDS = [
    "preso em flagrante estupro",
    "acusado de estupro",
    "preso por pedofilia",
    "suspeito de abuso sexual",
    "condenado por exploração sexual",
    "mandado de prisão estupro",
    "investigado por abuso infantil",
    "foragido estupro vulneravel",
    "réu por estupro de vulneravel",
    "identificado como autor do abuso",
    "condenado a prisão por estupro",
    "sentença condenatória estupro",
    "policia prende homem acusado de estupro",
    "acusado de estupro coletivo",
    "trafico de crianças",
    "exploração sexual infantil",
    "aliciamento de menores internet",
    "pornografia infantil prisão",
    "favorecimento da prostituição infantil",
    "turismo sexual infantil",
    "predador sexual preso",
    "violência sexual contra vulnerável",
    "estupro de vulnerável prisão",
    "abuso sexual mediante fraude",
    "importunação sexual preso"
]

STATES = ["SP", "RJ", "PR", "GO"] # Expanded to include all target states

def extract_name(text: str) -> Optional[str]:
    """
    Extract potential names from text using heuristics.
    """
    if not text:
        return None
        
    # Remove common prefixes/suffixes to clean up
    text_clean = text.replace("Policia Civil", "").replace("Policia Militar", "")
    text_clean = text_clean.replace("Delegacia", "").replace("Justiça", "")
    
    # Enhanced patterns for Portuguese names
    patterns = [
        # "O advogado Fulano de Tal"
        r"(?:advogado|juiz|promotor|réu|acusado|vítima|suspeito|preso|condenado|denunciado) (?:de )?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        # "Fulano de Tal, de 30 anos"
        r"([A-Z][a-z]+(?: [A-Z][a-z]+)+), de \d{1,2} anos",
        # "prisão de Fulano de Tal"
        r"prisão de ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        # "contra Fulano de Tal"
        r"contra ([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        # Simple Name Surname (fallback, risk of false positives, so kept last and strict)
        r" ([A-Z][a-z]+ [A-Z][a-z]+) "
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_clean)
        if match:
            name = match.group(1).strip()
            # print(f"      [DEBUG] Potential name found: '{name}' in text: '{text_clean[:50]}...'")
            # Filter out obvious false positives
    blocklist = [
        "Policia", "Delegacia", "Justiça", "Tribunal", "Ministério", "Publico", "Defensoria",
        "Rio de Janeiro", "São Paulo", "Mato Grosso", "Minas Gerais", "Espirito Santo",
        "Santa Catarina", "Rio Grande", "Distrito Federal",
        "Bom Prato", "Blue Tree", "Smart Sampa", "Lei Seca", "Cabo Frio", "Zona Norte",
        "Zona Sul", "Zona Leste", "Zona Oeste",
        "Estados Unidos", "Reino Unido",
        "Hospital", "Santa Casa", "Prefeitura", "Governo", "Estado", "Uniao",
        "Civil", "Militar", "Federal", "Guarda",
        "Avenida", "Rua", "Praça", "Alameda", "Estrada", "Rodovia", "Via", "Largo",
        "Jardim", "Parque", "Vila", "Cidade", "Bairro", "Centro"
    ]
    
    if len(name) > 5 and all(b not in name for b in blocklist):
        return name
    return None

def populate_targets():
    db = SessionLocal()
    rpa = GoogleNewsRPA()
    
    print(f"Starting target population for {len(STATES)} states and {len(KEYWORDS)} keywords...")
    
    total_new_targets = 0
    
    try:
        for state in STATES:
            print(f"\nProcessing State: {state}")
            for keyword in KEYWORDS:
                query = f"{keyword} {state}"
                print(f"  Searching: {query}")
                
                try:
                    result_dict = rpa.search(query, max_pages=1)
                    
                    if result_dict.get("status") != "success":
                        print(f"    Failed: {result_dict.get('error')}")
                        continue
                        
                    items = result_dict.get("results", [])
                    print(f"    Found {len(items)} news items")
                    
                    for item in items:
                        try:
                            # 1. Save News
                            news = News(
                                title=item.get("title"),
                                url=item.get("url"),
                                source=item.get("source"),
                                snippet=item.get("snippet"),
                                published_date=item.get("published_date"),
                                city=item.get("city"),
                                state=item.get("state") or state
                            )
                            # Check duplicate in DB
                            existing = db.query(News).filter(News.url == news.url).first()
                            if not existing:
                                db.add(news)
                                db.commit() # Commit immediately to avoid Unique violation in next iter if same url appears
                            else:
                                db.rollback() # Clear session just in case
                            
                            # 2. Extract Name
                            name_from_title = extract_name(item.get("title"))
                            name_from_snippet = extract_name(item.get("snippet"))
                            
                            target_name = name_from_title or name_from_snippet
                            
                            if target_name:
                                # Check if target exists
                                existing_target = db.query(Target).filter(Target.name == target_name).first()
                                if not existing_target:
                                    print(f"    [+] New Target found: {target_name}")
                                    new_target = Target(
                                        name=target_name,
                                        source=f"News: {item.get('source')} - {item.get('title')[:30]}..."
                                    )
                                    db.add(new_target)
                                    db.commit()
                                    total_new_targets += 1
                                else:
                                    db.rollback()
                        except Exception as item_error:
                             # print(f"      Error item: {item_error}")
                             db.rollback()
                             continue

                except Exception as e:
                    print(f"    Error processing query {query}: {e}")
                    db.rollback()
                    continue
                
                # Sleep to be nice to Google
                time.sleep(2)
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        db.close()
        print(f"\nFinished. Total new targets added: {total_new_targets}")

if __name__ == "__main__":
    populate_targets()
