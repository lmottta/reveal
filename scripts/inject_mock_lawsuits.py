import sys
import os
import json
import random
from datetime import datetime, timedelta

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

from app.db.session import SessionLocal
from app.models.lawsuit import Target, Lawsuit

def generate_cnj():
    # Format: NNNNNNN-DD.AAAA.J.TR.OOOO
    # Ex: 0012345-67.2023.8.26.0050
    seq = f"{random.randint(1000, 99999):07d}"
    dig = f"{random.randint(1, 99):02d}"
    year = random.randint(2018, 2023)
    just = "8" # Justiça Estadual
    trib = random.choice(["26", "19", "16", "09"]) # SP, RJ, PR, PR
    orig = f"{random.randint(1, 100):04d}"
    return f"{seq}{dig}{year}{just}{trib}{orig}"

def inject_mock_lawsuits():
    print("===============================================================")
    print("🦅 AARON DATA HUNTER - INJETANDO DADOS PROCESSUAIS DE ALVOS 🦅")
    print("Simulação de dados processuais para fins de demonstração analítica")
    print("===============================================================\n")

    db = SessionLocal()
    
    targets = db.query(Target).all()
    count = 0
    
    subjects = [
        "Estupro de Vulnerável",
        "Importunação Sexual",
        "Exploração Sexual Infantil",
        "Tráfico de Pessoas para Exploração Sexual",
        "Produção de Material Pornográfico Infantil"
    ]
    
    classes = [
        "Ação Penal - Procedimento Ordinário",
        "Inquérito Policial",
        "Prisão Preventiva"
    ]
    
    states = ["TJSP", "TJRJ", "TJPR", "TJGO", "TJBA", "TJSC"]
    
    for target in targets:
        # Se já tem processos associados, ignora? (Não temos vinculo direto além do nome nas partes)
        # Vamos apenas injetar 1 a 3 processos para cada alvo recém criado
        
        num_lawsuits = random.randint(1, 3)
        for _ in range(num_lawsuits):
            cnj = generate_cnj()
            
            # Checar duplicidade
            if db.query(Lawsuit).filter(Lawsuit.cnj == cnj).first():
                continue
                
            state = random.choice(states)
            subject = random.choice(subjects)
            class_type = random.choice(classes)
            
            parties = {
                "Polo Ativo": ["Ministério Público do Estado"],
                "Polo Passivo": [target.name]
            }
            
            # Data de distribuição aleatória nos últimos 5 anos
            days_ago = random.randint(10, 1800)
            dist_date = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")
            
            lawsuit = Lawsuit(
                cnj=cnj,
                tribunal=state,
                class_type=class_type,
                subject=subject,
                status="Ativo",
                distribution_date=dist_date,
                court=f"Vara Criminal de {state}",
                judge="Juiz de Direito",
                parties=json.dumps(parties),
                movements=json.dumps([{"data": dist_date, "descricao": "Distribuição do processo"}])
            )
            
            db.add(lawsuit)
            count += 1
            print(f"[+] Injetado Processo {cnj} para o Alvo: {target.name} ({subject})")
            
    try:
        db.commit()
        print(f"\n[!] Sucesso: {count} processos injetados no banco de dados.")
    except Exception as e:
        db.rollback()
        print(f"\n[X] Erro ao salvar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inject_mock_lawsuits()
