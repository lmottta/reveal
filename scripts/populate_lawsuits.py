import sys
import os
import json
import time
import re

# Add backend directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, "..", "backend")
sys.path.append(backend_dir)

from app.db.session import SessionLocal
from app.models.lawsuit import Target, Lawsuit
from app.rpa.config import get_rpa_for_state, TRIBUNAL_CONFIG

# Estados prioritários (grandes centros + Projudi que estamos focando)
TARGET_STATES = ["RJ", "SP", "PR", "GO", "MG", "RS", "SC", "BA", "PE", "DF"]

def clean_cnj(text):
    if not text:
        return None
    return re.sub(r"\D", "", text)

def populate_lawsuits():
    print("=== INICIANDO POPULAÇÃO DE PROCESSOS (CONSULTA ASSISTIDA) ===")
    db = SessionLocal()
    
    # Buscar alvos não processados ou todos se for recarga
    # targets = db.query(Target).filter(Target.is_processed == False).all()
    targets = db.query(Target).all() 
    
    print(f"Alvos encontrados: {len(targets)}")
    
    for target in targets:
        print(f"\n>>> Processando Alvo: {target.name} (Tipo: {target.type})")
        
        for state in TARGET_STATES:
            print(f"  [{state}] Iniciando busca...")
            
            try:
                rpa = get_rpa_for_state(state)
            except Exception as e:
                print(f"  [{state}] Erro ao instanciar RPA: {e}")
                continue
            
            if not rpa:
                print(f"  [{state}] RPA não configurado.")
                continue
                
            try:
                # Executar busca
                # Pequeno delay para evitar rate limit global agressivo
                time.sleep(1)
                
                result = rpa.search(target.name)
                
                status = result.get("status")
                found = result.get("found", False)
                msg = result.get("msg", "")
                
                if status == "success" and found:
                    items = result.get("results", [])
                    print(f"  [{state}] SUCESSO: {len(items)} processos encontrados.")
                    
                    for item in items:
                        # Extrair CNJ (chave pode variar: 'processo', 'cnj', ou extrair do 'raw')
                        raw_cnj = item.get("processo") or item.get("cnj")
                        
                        # Tentar extrair de 'raw' se não tiver cnj explícito
                        if not raw_cnj and item.get("raw"):
                             match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", item.get("raw"))
                             if match:
                                 raw_cnj = match.group(0)

                        if not raw_cnj:
                            print(f"    [WARN] Item sem CNJ identificável: {str(item)[:50]}...")
                            continue
                            
                        clean_num = clean_cnj(raw_cnj)
                        
                        # Verificar duplicidade no banco
                        existing = db.query(Lawsuit).filter(Lawsuit.cnj == clean_num).first()
                        
                        if not existing:
                            # Preparar dados para salvar
                            # Usar .get com defaults para evitar erros
                            lawsuit = Lawsuit(
                                cnj=clean_num, # Salvar apenas números para consistência
                                tribunal=state,
                                class_type=item.get("classe", "Não informado"),
                                subject=item.get("assunto", "Não informado"),
                                status=item.get("situacao", "Ativo"),
                                distribution_date=item.get("distribuicao"),
                                court=item.get("vara", item.get("origem", "Tribunal")),
                                judge=item.get("juiz"),
                                parties=json.dumps(item.get("partes", {})), # Converter dict para JSON string
                                movements=json.dumps(item.get("movimentacoes", [])), # Converter list para JSON string
                                raw_content=json.dumps(item, default=str) # Salvar tudo que veio para auditoria
                            )
                            
                            db.add(lawsuit)
                            try:
                                db.commit()
                                print(f"    [SAVE] Processo {raw_cnj} salvo.")
                            except Exception as e:
                                db.rollback()
                                print(f"    [ERROR] Falha ao salvar {raw_cnj}: {e}")
                        else:
                            print(f"    [SKIP] Processo {raw_cnj} já existe no banco.")
                            
                elif status == "error":
                    print(f"  [{state}] ERRO RPA: {result.get('error') or msg}")
                else:
                    print(f"  [{state}] Nenhum resultado: {msg}")
                    
            except Exception as e:
                print(f"  [{state}] EXCEÇÃO CRÍTICA NA BUSCA: {e}")
                # Não abortar o script inteiro, apenas este estado
        
        # Marcar alvo como processado (opcional, pode querer reprocessar periodicamente)
        # target.is_processed = True
        # db.commit()
        
    db.close()
    print("\n=== FINALIZADO ===")

if __name__ == "__main__":
    populate_lawsuits()
