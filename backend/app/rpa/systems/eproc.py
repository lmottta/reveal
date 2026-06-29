from typing import Dict, Any, List
import re
import time
from .base_system import BaseSystemRPA
from bs4 import BeautifulSoup

class EprocRPA(BaseSystemRPA):
    """
    Implementação genérica para tribunais que utilizam o sistema Eproc (RS, SC, TO).
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
                
                # Eproc geralmente tem um campo para consulta pública de processo
                input_selector = "input[name='txtNumProcesso'], input#txtNumProcesso"
                
                clean_query = re.sub(r"\D", "", query)
                formatted_query = f"{clean_query[:7]}-{clean_query[7:9]}.{clean_query[9:13]}.{clean_query[13]}.{clean_query[14:16]}.{clean_query[16:]}"
                
                if page.is_visible(input_selector):
                    page.fill(input_selector, formatted_query)
                    
                    if page.is_visible("#btnConsulta"):
                        page.click("#btnConsulta")
                    elif page.is_visible("input[value='Consultar']"):
                        page.click("input[value='Consultar']")
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
                        "sistema": "Eproc",
                        "url": page.url
                    }
                    
                    if "Processo não encontrado" in html or "Nenhum registro encontrado" in html:
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
                    # Debug para identificar seletores diferentes em outros estados
                    print(f"[DEBUG-EPROC] {self.tribunal_name} URL: {page.url}")
                    inputs = page.locator("input").all()
                    input_names = [i.get_attribute("name") for i in inputs]
                    input_ids = [i.get_attribute("id") for i in inputs]
                    print(f"[DEBUG-EPROC] {self.tribunal_name} Inputs encontrados: Names={input_names}, IDs={input_ids}")

                    # Screenshot para debug
                    try:
                        page.screenshot(path=f"error_eproc_{self.tribunal_name}.png")
                        print(f"[DEBUG-EPROC] Screenshot salvo: error_eproc_{self.tribunal_name}.png")
                    except:
                        pass

                    return {
                        "tribunal": self.tribunal_name,
                        "status": "error",
                        "msg": "Campo de busca não encontrado"
                    }

            except Exception as e:
                try:
                    if 'page' in locals():
                        page.screenshot(path=f"error_eproc_exception_{self.tribunal_name}.png")
                except:
                    pass
                return {
                    "tribunal": self.tribunal_name,
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
