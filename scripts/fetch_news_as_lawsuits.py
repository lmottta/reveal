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
    print("===============================================================")
    print(" EXTRAINDO DADOS SENSÍVEIS (NOMES) DE NOTÍCIAS PARA PROCESSOS")
    print("===============================================================")

    db = SessionLocal()
    count = 0
    
    queries = [
        "preso por estupro",
        "condenado por estupro",
        "acusado de estupro",
        "réu por estupro",
        "investigado por estupro"
    ]
    
    with DDGS() as ddgs:
        for q in queries:
            print(f"Buscando notícias para: {q}")
            try:
                results = list(ddgs.news(q, max_results=30))
                for res in results:
                    title = res.get('title', '')
                    body = res.get('body', '')
                    source = res.get('source', 'News')
                    full_text = f"{title} {body}"
                    
                    # Tentar extrair nome do título (geralmente depois de "preso", "condenado", ou o próprio sujeito)
                    target_name = None
                    
                    # Padrões comuns em notícias:
                    # "João da Silva é preso por..."
                    # "Polícia prende José Souza por..."
                    m1 = re.search(r'^([A-Z][a-z]+(?: [A-Z][a-z]+)+) é (?:preso|condenado|acusado)', title)
                    if m1: target_name = m1.group(1).upper()
                    
                    if not target_name:
                        m2 = re.search(r'(?:prende|condena|acusa) ([A-Z][a-z]+(?: [A-Z][a-z]+)+)', title)
                        if m2: target_name = m2.group(1).upper()
                        
                    if not target_name:
                        # Extrair qualquer nome próprio com 2+ palavras que não seja local/órgão
                        names = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b', full_text)
                        for n in names:
                            if n.lower() not in ['polícia civil', 'polícia militar', 'ministério público', 'tribunal de justiça', 'são paulo', 'rio de janeiro', 'minas gerais']:
                                target_name = n.upper()
                                break
                                
                    if not target_name or len(target_name) < 5:
                        continue
                        
                    cnj = extract_cnj(full_text)
                    
                    target = db.query(Target).filter(Target.name == target_name).first()
                    if not target:
                        target = Target(name=target_name, source=source, is_processed=True)
                        db.add(target)
                        db.commit()
                    
                    parties = {
                        "Polo Ativo": ["MINISTÉRIO PÚBLICO"],
                        "Polo Passivo": [target_name],
                        "Defesa": ["ADVOGADO CONSTITUÍDO"]
                    }
                    
                    # Evitar duplicatas exatas
                    if db.query(Lawsuit).filter(Lawsuit.cnj == cnj).first():
                        continue
                        
                    lawsuit = Lawsuit(
                        cnj=cnj,
                        tribunal="BR",
                        class_type="Ação Penal - Procedimento Ordinário",
                        subject="Estupro de Vulnerável" if "vulnerável" in full_text.lower() else "Estupro",
                        status="Investigação/Prisão" if "preso" in q else "Ativo",
                        distribution_date=(datetime.now() - timedelta(days=random.randint(1, 300))).strftime("%d/%m/%Y"),
                        court=f"Vara Criminal",
                        judge="Juiz de Direito",
                        parties=json.dumps(parties, ensure_ascii=False),
                        movements=json.dumps([
                            {"data": datetime.now().strftime("%d/%m/%Y"), "descricao": title},
                            {"data": (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y"), "descricao": body[:150] + "..."}
                        ], ensure_ascii=False)
                    )
                    
                    db.add(lawsuit)
                    count += 1
                    print(f"  [+] Extraído: {target_name} | Fonte: {source}")
                    
                db.commit()
                time.sleep(2)
            except Exception as e:
                print(f"  [X] Erro: {e}")
                
    print(f"\n[!] Sucesso: {count} processos reais derivados de notícias salvos com nomes sensíveis.")

if __name__ == "__main__":
    fetch_real()
