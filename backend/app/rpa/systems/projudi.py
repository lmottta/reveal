from typing import Dict, Any, List
import re
import time
import base64
from app.core.captcha_solver import CaptchaSolver
from .base_system import BaseSystemRPA
from bs4 import BeautifulSoup

class ProjudiRPA(BaseSystemRPA):
    """
    Implementação genérica para tribunais que utilizam o sistema Projudi (PR, GO, RR, AM, PA).
    """

    def search(self, query: str) -> Dict[str, Any]:
        if not self.validate_input(query):
             return {
                "tribunal": self.tribunal_name,
                "status": "error",
                "msg": "CNJ inválido"
            }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            return {"error": f"Playwright not available: {str(e)}", "results": []}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            page = context.new_page()

            try:
                page.goto(self.base_url, timeout=30000)
                
                # DEBUG: Onde estamos?
                print(f"[DEBUG-PROJUDI] URL: {page.url}")
                try:
                    print(f"[DEBUG-PROJUDI] Title: {page.title()}")
                except:
                    pass
                
                # Projudi geralmente tem um campo para número do processo na consulta pública
                # Seletores comuns:
                # - input[name='numeroProcesso']
                # - input[id='numeroProcesso']
                
                input_selector = "input[name='numeroProcesso'], input[id='numeroProcesso'], input[name='filtro.numeroProcesso']"

                # Verificar se estamos na tela de login e tentar navegar para consulta pública
                if "tjrr.jus.br" in self.base_url:
                     # Tentativa direta para TJRR
                     target_url = "https://projudi.tjrr.jus.br/projudi/paginas/consulta_publica.jsp"
                     print(f"[DEBUG-PROJUDI] Navegando para consulta pública direta do TJRR: {target_url}")
                     page.goto(target_url, timeout=30000)

                elif "tjgo.jus.br" in self.base_url:
                     # Tentativa direta para TJGO (URL atualizada 2026)
                     target_url = "https://projudi.tjgo.jus.br/BuscaProcesso"
                     print(f"[DEBUG-PROJUDI] Navegando para consulta pública direta do TJGO: {target_url}")
                     try:
                        page.goto(target_url, timeout=30000)
                        # TJGO tem inputs específicos
                        input_selector = "input[id='ProcessoNumero'], input[name='ProcessoNumero']"
                     except:
                        print("[DEBUG-PROJUDI] Falha na URL direta TJGO, tentando raiz...")
                        page.goto("https://projudi.tjgo.jus.br/", timeout=30000)
                
                elif "login" in page.url or page.locator("input[name='j_username']").is_visible():
                    print(f"[DEBUG] Tela de login detectada em {page.url}. Tentando encontrar link de Consulta Pública...")
                    # Tentar links comuns de consulta pública
                    if page.get_by_text("Consulta Pública", exact=False).is_visible():
                        page.get_by_text("Consulta Pública", exact=False).click()
                    elif page.get_by_text("Consultas", exact=False).is_visible():
                        page.get_by_text("Consultas", exact=False).click()
                    
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        pass
                
                # Esperar frames carregarem
                try:
                    page.wait_for_load_state("networkidle")
                except:
                    pass
                
                # Listar frames para debug
                print(f"[DEBUG-PROJUDI] Total de frames: {len(page.frames)}")
                for f in page.frames:
                    try:
                        print(f"[DEBUG-PROJUDI] Frame: {f.name} - URL: {f.url}")
                    except:
                        pass

                clean_query = re.sub(r"\D", "", query)
                is_cnj = (len(clean_query) == 20)
                
                if is_cnj:
                    formatted_query = f"{clean_query[:7]}-{clean_query[7:9]}.{clean_query[9:13]}.{clean_query[13]}.{clean_query[14:16]}.{clean_query[16:]}"
                    
                    # Projudi às vezes pede campos separados. 
                    # Se for campo único:
                    if page.is_visible(input_selector):
                        page.fill(input_selector, formatted_query)
                        
                        # --- CAPTCHA HANDLING START ---
                        # Verificar se existe CAPTCHA antes de clicar
                        captcha_selectors = ["img[id*='captcha']", "img[src*='captcha']", "img[alt*='Captcha']", "img[src*='jcaptcha']"]
                        captcha_img_selector = None
                        for sel in captcha_selectors:
                            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                                captcha_img_selector = sel
                                break
                        
                        if captcha_img_selector:
                            print(f"[DEBUG-PROJUDI] CAPTCHA detectado: {captcha_img_selector}")
                            try:
                                solver = CaptchaSolver() # Usa configuração padrão (Auto/Local)
                                # Screenshot do elemento específico
                                captcha_bytes = page.locator(captcha_img_selector).first.screenshot()
                                solved_text = solver.solve_image(captcha_bytes)
                                
                                if solved_text:
                                    print(f"[DEBUG-PROJUDI] Solução Local: {solved_text}")
                                    # Input do captcha
                                    input_captcha_sel = None
                                    for inp in ["input[name*='captcha']", "input[id*='captcha']", "input[id='resposta']", "input[name='resposta']", "input[name='j_captcha_response']"]:
                                        if page.locator(inp).count() > 0:
                                            input_captcha_sel = inp
                                            break
                                    
                                    if input_captcha_sel:
                                        page.fill(input_captcha_sel, solved_text)
                                    else:
                                        print("[DEBUG-PROJUDI] Input de CAPTCHA não encontrado!")
                            except Exception as e:
                                print(f"[DEBUG-PROJUDI] Erro ao resolver CAPTCHA: {e}")
                        # --- CAPTCHA HANDLING END ---

                        # Tentar lidar com Turnstile/Captcha (espera explícita)
                        try:
                            # Esperar até 5s por um frame de turnstile
                            for _ in range(10):
                                turnstile_frames = [f for f in page.frames if "turnstile" in f.url or "challenge" in f.url]
                                if turnstile_frames:
                                    print(f"[DEBUG-PROJUDI] Turnstile detectado em {len(turnstile_frames)} frames. Tentando clicar...")
                                    for tf in turnstile_frames:
                                        try:
                                            # Tentar clicar no checkbox ou no body do iframe
                                            if tf.locator("input[type='checkbox']").is_visible():
                                                tf.click("input[type='checkbox']")
                                            else:
                                                tf.click("body")
                                            time.sleep(2)
                                        except: pass
                                    break
                                time.sleep(0.5)
                        except: pass
                        
                        # Botão pesquisar
                        if page.is_visible("#pesquisar"):
                            page.click("#pesquisar")
                        elif page.is_visible("input[value='Pesquisar']"):
                            page.click("input[value='Pesquisar']")
                        elif page.is_visible("#btnBuscar"): # TJGO Novo
                            page.click("#btnBuscar")
                        else:
                            page.press(input_selector, "Enter")
                        
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            pass
                        
                        html = page.content()
                        
                        process_data = {
                            "processo": formatted_query,
                            "tribunal": self.tribunal_name,
                            "sistema": "Projudi",
                            "url": page.url
                        }
                        
                        if "Nenhum registro encontrado" in html or "Processo Inexistente" in html:
                            return {
                                "tribunal": self.tribunal_name,
                                "status": "success",
                                "found": False,
                                "msg": "Processo não encontrado"
                            }
                        
                        return {
                            "tribunal": self.tribunal_name,
                            "status": "success",
                            "found": True,
                            "results": [process_data],
                            "msg": "Processo encontrado (extração simplificada)"
                        }
                    
                    else:
                        # Tentar ver se é estrutura de campos separados (Projudi antigo)
                        # NNNNNNN DD AAAA J TR OOOO
                        # Seletores comuns: numeroSequencial, numeroDigitoVerificador, ano
                        
                        found_separate_fields = False
                        
                        if page.is_visible("input[name*='numeroSequencial']") or page.is_visible("input[id*='numeroSequencial']"):
                             num_seq_sel = "input[name*='numeroSequencial']" if page.is_visible("input[name*='numeroSequencial']") else "input[id*='numeroSequencial']"
                             page.fill(num_seq_sel, clean_query[:7])
                             found_separate_fields = True
                        
                        if page.is_visible("input[name*='numeroDigitoVerificador']") or page.is_visible("input[id*='numeroDigitoVerificador']"):
                             dv_sel = "input[name*='numeroDigitoVerificador']" if page.is_visible("input[name*='numeroDigitoVerificador']") else "input[id*='numeroDigitoVerificador']"
                             page.fill(dv_sel, clean_query[7:9])
                             found_separate_fields = True
                             
                        if page.is_visible("input[name*='ano']") or page.is_visible("input[id*='ano']"):
                             ano_sel = "input[name*='ano']" if page.is_visible("input[name*='ano']") else "input[id*='ano']"
                             page.fill(ano_sel, clean_query[9:13])
                             found_separate_fields = True
                             
                        if found_separate_fields:
                            # Botão pesquisar
                            if page.is_visible("#pesquisar"):
                                page.click("#pesquisar")
                            elif page.is_visible("input[value='Pesquisar']"):
                                page.click("input[value='Pesquisar']")
                            elif page.is_visible("button[id*='pesquisar']"):
                                 page.click("button[id*='pesquisar']")
                            else:
                                page.keyboard.press("Enter")
                                
                            try:
                                page.wait_for_load_state("networkidle", timeout=10000)
                            except:
                                pass
                            
                            html = page.content()
                            process_data = {
                                "processo": formatted_query,
                                "tribunal": self.tribunal_name,
                                "sistema": "Projudi",
                                "url": page.url
                            }
                            
                            if "Nenhum registro encontrado" in html or "Processo Inexistente" in html:
                                return {
                                    "tribunal": self.tribunal_name,
                                    "status": "success",
                                    "found": False,
                                    "msg": "Processo não encontrado"
                                }
                            
                            return {
                                "tribunal": self.tribunal_name,
                                "status": "success",
                                "found": True,
                                "results": [process_data],
                                "msg": "Processo encontrado (campos separados)"
                            }
                
                else:
                    # Busca por NOME
                    print(f"[DEBUG-PROJUDI] Iniciando busca por nome: {query}")
                    
                    # Tentar encontrar campo de nome (incluindo iframes)
                    name_selectors = [
                        "input[name='nomeParte']", 
                        "input[id='nomeParte']", 
                        "input[name='filtro.nomeParte']", 
                        "input[id='filtro.nomeParte']",
                        "input[name*='nome']",
                        "input[id*='nome']",
                        "input[name='parameter[0]']", # TJPR antigo as vezes usa isso
                        "input[id='NomeParte']", # TJGO Novo
                        "input[name='NomeParte']" # TJGO Novo
                    ]
                    
                    target_frame = None
                    name_input = None
                    
                    # 1. Tentar na página principal
                    for sel in name_selectors:
                        if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                            name_input = sel
                            target_frame = page
                            break
                    
                    # 2. Se não achou, tentar nos frames
                    if not name_input:
                        print(f"[DEBUG-PROJUDI] Procurando em {len(page.frames)} frames...")
                        # Esperar um pouco para frames carregarem
                        page.wait_for_timeout(3000) 
                        
                        for i, frame in enumerate(page.frames):
                            try:
                                print(f"[DEBUG-PROJUDI] Inspecionando Frame {i}: {frame.name} - {frame.url}")
                                # Dump frame content for debug if it's likely the right one but failing
                                if "consulta" in frame.url or "publica" in frame.url:
                                    try:
                                        with open(f"debug_projudi_frame_{i}.html", "w", encoding="utf-8") as f:
                                            f.write(frame.content())
                                    except:
                                        pass

                                for sel in name_selectors:
                                    if frame.locator(sel).count() > 0:
                                        # Visibilidade pode ser tricky em frames, as vezes is_visible() retorna false mas está lá
                                        name_input = sel
                                        target_frame = frame
                                        print(f"[DEBUG-PROJUDI] Encontrado input '{sel}' no frame '{frame.name}'")
                                        break
                                if name_input:
                                    break
                            except Exception as e:
                                print(f"[DEBUG-PROJUDI] Erro inspecionando frame {i}: {e}")
                                pass
                    
                    if not name_input:
                        # DEBUG: Listar inputs disponíveis para diagnóstico (incluindo frames)
                        all_inputs = page.locator("input").all()
                        debug_info = []
                        for inp in all_inputs:
                            try:
                                debug_info.append(f"MAIN: name={inp.get_attribute('name')}, id={inp.get_attribute('id')}")
                            except:
                                pass
                        
                        for frame in page.frames:
                            try:
                                f_inputs = frame.locator("input").all()
                                for inp in f_inputs:
                                    debug_info.append(f"FRAME({frame.name}): name={inp.get_attribute('name')}")
                            except:
                                pass
                                
                        print(f"[DEBUG-PROJUDI] Inputs na página: {debug_info}")

                        return {
                            "tribunal": self.tribunal_name,
                            "status": "error",
                            "msg": "Campo de nome não encontrado"
                        }
                    
                    target_frame.fill(name_input, query)
                    
                    # --- CAPTCHA HANDLING (Same logic, adapted for frame) ---
                    captcha_selectors = ["img[id*='captcha']", "img[src*='captcha']", "img[alt*='Captcha']", "img[src*='jcaptcha']"]
                    captcha_img_selector = None
                    for sel in captcha_selectors:
                        if target_frame.locator(sel).count() > 0 and target_frame.locator(sel).first.is_visible():
                            captcha_img_selector = sel
                            break
                    
                    if captcha_img_selector:
                        print(f"[DEBUG-PROJUDI] CAPTCHA detectado: {captcha_img_selector}")
                        try:
                            solver = CaptchaSolver()
                            captcha_bytes = target_frame.locator(captcha_img_selector).first.screenshot()
                            solved_text = solver.solve_image(captcha_bytes)
                            
                            if solved_text:
                                print(f"[DEBUG-PROJUDI] Solução Local: {solved_text}")
                                input_captcha_sel = None
                                for inp in ["input[name*='captcha']", "input[id*='captcha']", "input[id='resposta']", "input[name='resposta']", "input[name='j_captcha_response']"]:
                                    if target_frame.locator(inp).count() > 0:
                                        input_captcha_sel = inp
                                        break
                                
                                if input_captcha_sel:
                                    target_frame.fill(input_captcha_sel, solved_text)
                        except Exception as e:
                            print(f"[DEBUG-PROJUDI] Erro CAPTCHA: {e}")
                    # --- END CAPTCHA ---

                    # Botão pesquisar
                    if target_frame.is_visible("#pesquisar"):
                        target_frame.click("#pesquisar")
                    elif target_frame.is_visible("input[value='Pesquisar']"):
                        target_frame.click("input[value='Pesquisar']")
                    elif target_frame.is_visible("button[id*='pesquisar']"):
                         target_frame.click("button[id*='pesquisar']")
                    else:
                        target_frame.press(name_input, "Enter")
                    
                    # Esperar tabela de resultados
                    try:
                        target_frame.wait_for_selector("table", timeout=15000)
                    except:
                        pass
                    
                    html = target_frame.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results = []
                    
                    # Parsing genérico de tabelas
                    tables = soup.find_all("table")
                    for table in tables:
                        rows = table.find_all("tr")
                        if len(rows) > 1: # Header + Data
                            for row in rows:
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    row_text = row.get_text(" ", strip=True)
                                    # Validar se parece um processo (NNNNNNN-DD.AAAA...)
                                    match = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", row_text)
                                    if match:
                                        proc_num = match.group(0)
                                        results.append({
                                            "processo": proc_num,
                                            "cnj": re.sub(r"\D", "", proc_num),
                                            "tribunal": self.tribunal_name,
                                            "descricao": row_text[:200], # Snippet
                                            "origem": f"{self.tribunal_name} (Projudi)"
                                        })
                    
                    return {
                        "tribunal": self.tribunal_name,
                        "status": "success",
                        "found": len(results) > 0,
                        "results": results,
                        "msg": f"Encontrados {len(results)} processos"
                    }

            except Exception as e:
                return {
                    "tribunal": self.tribunal_name,
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
