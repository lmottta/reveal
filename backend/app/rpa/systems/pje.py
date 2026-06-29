from typing import Dict, Any, List
import re
import time
import base64
from .base_system import BaseSystemRPA
from bs4 import BeautifulSoup
from app.core.captcha_solver import solver

class PJeRPA(BaseSystemRPA):
    """
    Implementação genérica para tribunais que utilizam o sistema PJe (Processo Judicial Eletrônico).
    Baseado na interface JSF/Seam comum (listView.seam).
    """

    def search(self, query: str) -> Dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            return {"error": f"Playwright not available: {str(e)}", "results": []}

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            try:
                # Navegar para URL base
                page.goto(self.base_url, timeout=60000)
                
                # PJe geralmente usa frames ou JS pesado.
                # Esperar input de número do processo
                # Seletores comuns do PJe:
                # - id='fPP:numProcesso-inputNumeroProcessoDecoration:numProcesso-inputNumeroProcesso'
                # - id='fPP:numeroProcesso:numeroProcesso'
                
                input_selector = None
                for selector in [
                    "input[id*='numProcesso-inputNumeroProcesso']", 
                    "input[id*='numeroProcesso']",
                    "input[title='Número do Processo']"
                ]:
                    if page.locator(selector).count() > 0:
                        input_selector = selector
                        break
                
                if not input_selector:
                     # Tentar esperar um pouco mais se for JS lento
                     try:
                         page.wait_for_selector("input[type='text']", timeout=10000)
                         # Tentar novamente
                         for selector in [
                            "input[id*='numProcesso-inputNumeroProcesso']", 
                            "input[id*='numeroProcesso']"
                        ]:
                            if page.locator(selector).count() > 0:
                                input_selector = selector
                                break
                     except:
                         pass

                if input_selector:
                    # Limpar formatação se necessário, mas PJe geralmente aceita com ou sem
                    # Vamos enviar formatado se possível, ou limpo se falhar
                    clean_query = re.sub(r"\D", "", query)
                    # Formatar CNJ: NNNNNNN-DD.AAAA.J.TR.OR
                    formatted_query = f"{clean_query[:7]}-{clean_query[7:9]}.{clean_query[9:13]}.{clean_query[13]}.{clean_query[14:16]}.{clean_query[16:]}"
                    
                    page.fill(input_selector, formatted_query)
                    
                    # Botão pesquisar
                    # id='fPP:searchProcessos'
                    # id='fPP:j_id132:j_id133' (variável)
                    # Vamos buscar por texto ou tipo submit
                    search_btn = None
                    if page.locator("input[id*='searchProcessos']").count() > 0:
                        search_btn = "input[id*='searchProcessos']"
                    elif page.locator("input[value='Pesquisar']").count() > 0:
                        search_btn = "input[value='Pesquisar']"
                    
                    if search_btn:
                        page.click(search_btn)
                    else:
                        page.keyboard.press("Enter")
                    
                    # Esperar resultados
                    # PJe usa RichFaces, então pode ter ajax
                    try:
                        # Esperar tabela de resultados ou mensagem
                        page.wait_for_selector(".rich-table, .infra-table, .alert-info, .aviso-erro", timeout=30000)
                    except:
                        pass
                    
                    content = page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    results = []
                    
                    # Extrair tabela
                    # PJe antigo: rich-table
                    # PJe novo: infra-table
                    tables = soup.find_all("table", class_=["rich-table", "infra-table"])
                    for table in tables:
                        rows = table.find_all("tr")
                        for row in rows:
                            cols = row.find_all("td")
                            if len(cols) > 2:
                                text_row = row.get_text(" ", strip=True)
                                if clean_query[:7] in text_row or formatted_query in text_row:
                                     results.append({
                                        "processo": formatted_query,
                                        "descricao": text_row[:200] + "...",
                                        "origem": f"{self.tribunal_name} (PJe)",
                                        "link": self.base_url
                                    })
                    
                    if not results:
                        # Verificar se abriu detalhe direto (pouco comum no PJe público, mas possível)
                        if formatted_query in soup.get_text():
                             results.append({
                                "processo": formatted_query,
                                "descricao": "Possível detalhe do processo encontrado (PJe)",
                                "origem": f"{self.tribunal_name} (PJe)",
                                "link": self.base_url
                            })

                    return {
                        "tribunal": self.tribunal_name,
                        "status": "success",
                        "query": query,
                        "results": results
                    }

                else:
                    # DEBUG
                    print(f"[DEBUG-PJE] URL: {page.url}")
                    try:
                        print(f"[DEBUG-PJE] Title: {page.title()}")
                    except:
                        pass
                        
                    if page.locator("img[id*='captcha']").count() > 0 or page.get_by_text("Digite os caracteres", exact=False).is_visible():
                        print(f"[DEBUG-PJE] CAPTCHA detectado em {self.tribunal_name}!")
                        
                        screenshot_b64 = ""
                        screenshot_bytes = None
                        
                        try:
                            # Tentar focar no elemento do captcha para screenshot limpo
                            captcha_img = page.locator("img[id*='captcha']").first
                            if captcha_img.is_visible():
                                screenshot_bytes = captcha_img.screenshot(type="png")
                            else:
                                screenshot_bytes = page.screenshot(type="png")
                                
                            page.screenshot(path=f"error_captcha_{self.tribunal_name}.png")
                            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                        except Exception as e:
                            print(f"[DEBUG-PJE] Erro ao capturar screenshot: {e}")
                            pass
                        
                        # TENTATIVA DE RESOLUÇÃO AUTOMÁTICA (INTERNA/EXTERNA)
                        solved_text = None
                        if screenshot_bytes:
                            print(f"[DEBUG-PJE] Tentando resolver CAPTCHA automaticamente...")
                            solved_text = solver.solve_image(screenshot_bytes)
                            
                        if solved_text:
                            print(f"[DEBUG-PJE] CAPTCHA Resolvido: {solved_text}")
                            try:
                                # Tentar preencher
                                # Seletores comuns de input de captcha no PJe
                                captcha_input = None
                                for sel in ["input[id*='captcha']", "input[name*='captcha']", "input[title*='texto da imagem']"]:
                                    if page.locator(sel).count() > 0:
                                        captcha_input = sel
                                        break
                                
                                if captcha_input:
                                    page.fill(captcha_input, solved_text)
                                    page.keyboard.press("Enter")
                                    page.wait_for_timeout(3000) # Esperar reload
                                    
                                    # Verificar se passou (se input de processo apareceu)
                                    if page.locator("input[id*='numProcesso']").count() > 0:
                                        print(f"[DEBUG-PJE] CAPTCHA bypass com sucesso!")
                                        # Recomeçar a busca (recursivo ou goto)
                                        # Simplificação: Retornar erro especial para retry imediato ou continuar fluxo aqui?
                                        # Como estamos no fim do fluxo, vamos retornar um status especial
                                        return {
                                            "tribunal": self.tribunal_name,
                                            "status": "retry", # Frontend/Backend deve lidar com isso
                                            "msg": "CAPTCHA resolvido automaticamente. Tente novamente.",
                                            "screenshot": None
                                        }
                            except Exception as ex:
                                print(f"[DEBUG-PJE] Falha ao inputar CAPTCHA: {ex}")

                        return {
                            "tribunal": self.tribunal_name,
                            "status": "error",
                            "msg": "CAPTCHA detectado no PJe. Validação humana necessária." if not solved_text else f"Falha ao submeter CAPTCHA resolvido ({solved_text}).",
                            "screenshot": f"data:image/png;base64,{screenshot_b64}" if screenshot_b64 else None
                        }

                    # Screenshot para debug de campo não encontrado
                    screenshot_b64 = ""
                    try:
                        page.screenshot(path=f"error_nofield_{self.tribunal_name}.png")
                        screenshot_bytes = page.screenshot(type="png")
                        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                        print(f"[DEBUG-PJE] Screenshot salvo: error_nofield_{self.tribunal_name}.png")
                    except:
                        pass

                    return {
                        "tribunal": self.tribunal_name,
                        "status": "error",
                        "msg": "Campo de busca não encontrado no PJe",
                        "screenshot": f"data:image/png;base64,{screenshot_b64}" if screenshot_b64 else None
                    }

            except Exception as e:
                try:
                    if 'page' in locals():
                        page.screenshot(path=f"error_exception_{self.tribunal_name}.png")
                except:
                    pass
                return {
                    "tribunal": self.tribunal_name,
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
