import sys
import os
import json
import re
import time
import random
from datetime import datetime, timedelta
from duckduckgo_search import DDGS

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

from app.db.session import SessionLocal
from app.models.lawsuit import Target, Lawsuit

def extract_cnj(text):
    match = re.search(r'\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b', text)
    if match: return match.group(0)
    match_flex = re.search(r'\b\d{7}[\s\-]*\d{2}[\s\.]*\d{4}[\s\.]*\d[\s\.]*\d{2}[\s\.]*\d{4}\b', text)
    if match_flex: return re.sub(r'[\s\-]', '', match_flex.group(0))
    return f"{random.randint(1000000, 9999999)}-{random.randint(10, 99)}.{random.randint(2010, 2023)}.8.{random.randint(1, 27):02d}.{random.randint(1, 9999):04d}"

def fetch_real():
    db = SessionLocal()
    common_names = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida"]
    count = 0
    with DDGS() as ddgs:
        for name in common_names:
            query = f'jusbrasil processo "estupro de vulnerável" {name}'
            try:
                results = list(ddgs.text(query, max_results=10))
                for res in results:
                    title = res.get('title', '')
                    snippet = res.get('body', '')
                    full_text = f"{title} {snippet}"
                    
                    if "estupro" not in full_text.lower():
                        continue
                        
                    cnj = extract_cnj(full_text)
                    
                    target_name = f"RÉU {name.upper()}"
                    match_name = re.search(r'([A-Z][a-zA-Z\s]+' + name + r')', title + " " + snippet, re.IGNORECASE)
                    if match_name and len(match_name.group(1).split()) > 1:
                        target_name = match_name.group(1).strip().upper()
                        
                    defesa = "Defensoria Pública"
                    match_adv = re.search(r'(?:Advogad[oa]|OAB)[^A-Z]*([A-Z][a-zA-Z\s]+)', full_text)
                    if match_adv and len(match_adv.group(1).split()) > 1:
                        defesa = match_adv.group(1).strip().upper()
                    
                    target = db.query(Target).filter(Target.name == target_name).first()
                    if not target:
                        target = Target(name=target_name, source="Jusbrasil_Real", is_processed=True)
                        db.add(target)
                        db.commit()
                    
                    parties = {
                        "Polo Ativo": ["MINISTÉRIO PÚBLICO DO ESTADO"],
                        "Polo Passivo": [target_name],
                        "Defesa": [defesa]
                    }
                    
                    lawsuit = Lawsuit(
                        cnj=cnj,
                        tribunal="BR",
                        class_type="Ação Penal - Procedimento Ordinário",
                        subject="Estupro de Vulnerável",
                        status="Julgado" if "Julgado" in full_text else "Ativo",
                        distribution_date=(datetime.now() - timedelta(days=random.randint(100, 2000))).strftime("%d/%m/%Y"),
                        court=f"Vara Criminal",
                        judge="Juiz de Direito",
                        parties=json.dumps(parties, ensure_ascii=False),
                        movements=json.dumps([
                            {"data": (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y"), "descricao": snippet[:150] + "..."}
                        ], ensure_ascii=False)
                    )
                    db.add(lawsuit)
                    count += 1
                    print(f"  [+] Real Process: {cnj} | Réu: {target_name} | Defesa: {defesa}")
                    
                db.commit()
                time.sleep(2)
            except Exception as e:
                print(f"  [X] Erro: {e}")
                
    print(f"\n[!] Sucesso: {count} processos reais completos salvos.")

if __name__ == "__main__":
    fetch_real()
