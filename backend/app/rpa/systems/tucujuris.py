from typing import Dict, Any, List
import re
import time
from .base_system import BaseSystemRPA
from bs4 import BeautifulSoup

class TucujurisRPA(BaseSystemRPA):
    """
    Implementação para o sistema Tucujuris (TJAP).
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
                
                # Tucujuris: Consulta Processual Unificada
                input_selector = "input[name='processo.numero'], input#numeroProcesso"
                
                clean_query = re.sub(r"\D", "", query)
                formatted_query = f"{clean_query[:7]}-{clean_query[7:9]}.{clean_query[9:13]}.{clean_query[13]}.{clean_query[14:16]}.{clean_query[16:]}"
                
                if page.is_visible(input_selector):
                    page.fill(input_selector, formatted_query)
                    
                    if page.is_visible("button#btn-consultar"):
                        page.click("button#btn-consultar")
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
                        "sistema": "Tucujuris",
                        "url": page.url
                    }
                    
                    if "Nenhum processo encontrado" in html:
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
                        "msg": "Processo encontrado"
                    }
                else:
                    # Debug
                    print(f"[DEBUG-TUCUJURIS] URL: {page.url}")
                    inputs = page.locator("input").all()
                    input_names = [i.get_attribute("name") for i in inputs]
                    input_ids = [i.get_attribute("id") for i in inputs]
                    print(f"[DEBUG-TUCUJURIS] Inputs encontrados: Names={input_names}, IDs={input_ids}")

                    return {
                        "tribunal": self.tribunal_name,
                        "status": "error",
                        "msg": "Campo de busca não encontrado"
                    }

            except Exception as e:
                return {
                    "tribunal": self.tribunal_name,
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
