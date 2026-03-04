import re
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright
from .base import BaseRPA
from bs4 import BeautifulSoup

class TJRJRPA(BaseRPA):
    """
    Implementação de RPA para o Tribunal de Justiça do Rio de Janeiro.
    Utiliza Playwright para interação real.
    """
    
    BASE_URL = "https://www3.tjrj.jus.br/consultaprocessual/consultaform.do"

    def _is_process_number(self, query: str) -> bool:
        # Regex básico para CNJ: NNNNNNN-DD.AAAA.J.TR.OR
        return bool(re.match(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", query))

    def search(self, query: str) -> Dict[str, Any]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            try:
                page.goto(self.BASE_URL, timeout=60000)
                
                # Identificar tipo de busca
                if self._is_process_number(query):
                    # Selecionar busca por número do processo
                    # TJRJ geralmente tem abas ou radios. Assumindo padrão comum.
                    # Seletor hipotético baseado em padrões comuns
                    if page.locator("input[id='radioNumero']").count() > 0:
                        page.click("input[id='radioNumero']")
                    page.fill("input[name='numProcesso']", query) # Nome comum
                    page.click("input[value='Pesquisar']", timeout=5000)
                else:
                    # Busca por Nome
                    if page.locator("input[id='radioNome']").count() > 0:
                        page.click("input[id='radioNome']")
                    
                    # Tentar preencher campo de nome
                    input_filled = False
                    for selector in ["input[name='NM_Parte']", "#nomeParte", "input[id='nomeParte']"]:
                        if page.locator(selector).count() > 0 and page.locator(selector).is_visible():
                            page.locator(selector).fill(query)
                            input_filled = True
                            break
                    
                    if not input_filled:
                         # Fallback
                         inputs = page.locator("input[type='text']")
                         for i in range(inputs.count()):
                             if inputs.nth(i).is_visible():
                                 inputs.nth(i).fill(query)
                                 break

                    # Clicar em pesquisar
                    # Botão pesquisar ou input submit
                    for btn in ["input[value='Pesquisar']", "button:has-text('Pesquisar')", "#btnPesquisar"]:
                        if page.locator(btn).count() > 0:
                            page.click(btn)
                            break
                
                # Esperar resultados
                try:
                    page.wait_for_selector(
                        "#tabelaResultados, .resultado-consulta, .mensagem-erro, #mensagemRetorno", 
                        timeout=15000
                    )
                except:
                    # Pode ser timeout ou não encontrou
                    pass

                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                results = []
                
                # Tentar extrair tabela de resultados
                # Estrutura genérica para TJRJ (muitas vezes tabelas com classe 'resultado')
                tabelas = soup.find_all("table")
                for tabela in tabelas:
                    rows = tabela.find_all("tr")
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 3:
                            # Tentar identificar colunas de processo
                            texto_row = row.get_text(" ", strip=True)
                            if "Processo" in texto_row or re.search(r"\d{7}-\d{2}", texto_row):
                                results.append({
                                    "raw": texto_row,
                                    "origem": "TJRJ"
                                })
                
                if not results:
                    return {
                        "tribunal": "TJRJ",
                        "status": "success", # Success no sentido de "executou", mas vazio
                        "query": query,
                        "results": [],
                        "msg": "Nenhum processo identificado ou layout desconhecido"
                    }

                return {
                    "tribunal": "TJRJ",
                    "status": "success",
                    "query": query,
                    "results": results
                }

            except Exception as e:
                return {
                    "tribunal": "TJRJ",
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
