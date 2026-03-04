import re
import time
import random
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from .base import BaseRPA

class TJMTRPA(BaseRPA):
    """
    Implementação de RPA para o Tribunal de Justiça de Mato Grosso (PJe/ClickJud).
    Utiliza Playwright para interação real.
    """
    
    BASE_URL = "https://consultaprocessual.tjmt.jus.br/"

    def _is_process_number(self, query: str) -> bool:
        # Regex básico para CNJ: NNNNNNN-DD.AAAA.J.TR.OR
        # TJMT é 8.11
        clean_query = re.sub(r"\D", "", query)
        return (len(clean_query) == 20 and "8.11" in query) or "8.11" in query

    def search(self, query: str) -> Dict[str, Any]:
        with sync_playwright() as p:
            # Launch browser (headless=True para produção)
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            try:
                page.goto(self.BASE_URL, timeout=60000)
                
                # Wait for input
                page.wait_for_selector("input[formcontrolname='numeroUnico']", timeout=30000)
                
                # Preencher número do processo
                # Simular digitação humana para garantir máscaras
                page.click("input[formcontrolname='numeroUnico']")
                for char in query:
                    page.keyboard.type(char)
                    time.sleep(random.uniform(0.01, 0.05)) # Digitação rápida mas humana
                
                # Clicar em Pesquisar
                page.click("button[type='submit']")
                
                # Esperar resultados
                # Pode ser "Nenhum processo encontrado" ou uma lista
                # Vamos esperar pelo componente de lista ou mensagem de erro
                try:
                    page.wait_for_selector("app-processo-list", timeout=30000)
                    # Dar um tempo extra para renderização do Angular
                    time.sleep(3)
                except:
                    return {
                        "tribunal": "TJMT",
                        "status": "error",
                        "query": query,
                        "results": [],
                        "msg": "Timeout aguardando resultados"
                    }

                # Extrair dados
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                results = []
                
                # Verificar se não encontrou nada
                if "Nenhum processo encontrado" in content:
                    return {
                        "tribunal": "TJMT",
                        "status": "success",
                        "query": query,
                        "results": [],
                        "msg": "Nenhum processo encontrado"
                    }
                
                # Tentar extrair cards de processo
                # Baseado na estrutura comum do PrimeNG/Angular nesse portal
                cards = soup.find_all("div", class_="prime-card")
                
                for card in cards:
                    text = card.get_text(" ", strip=True)
                    # Filtrar card de "Nenhum processo" se ainda existir
                    if "Nenhum processo encontrado" in text:
                        continue
                        
                    # Tentar estruturar minimamente
                    # Geralmente tem cabeçalho com número, classe, etc.
                    results.append({
                        "raw": text,
                        "origem": "TJMT",
                        "extra_data": {
                            "html": str(card)[:500] # Guardar um pouco do HTML para debug futuro
                        }
                    })
                
                return {
                    "tribunal": "TJMT",
                    "status": "success",
                    "query": query,
                    "results": results
                }

            except Exception as e:
                return {
                    "tribunal": "TJMT",
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
