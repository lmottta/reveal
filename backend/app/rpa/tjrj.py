import re
from typing import Dict, Any, List
# from playwright.sync_api import sync_playwright # Lazy import
from .base import BaseRPA
from bs4 import BeautifulSoup

class TJRJRPA(BaseRPA):
    """
    Implementação de RPA para o Tribunal de Justiça do Rio de Janeiro.
    Utiliza Playwright para interação real.
    """
    
    # BASE_URL = "https://www3.tjrj.jus.br/consultaprocessual/#/consultapublica"
    BASE_URL = "https://tjrj.pje.jus.br/pje/ConsultaPublica/listView.seam"

    def _is_process_number(self, query: str) -> bool:
        # Regex básico para CNJ: NNNNNNN-DD.AAAA.J.TR.OR
        return bool(re.match(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", query))

    def search(self, query: str) -> Dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            return {"error": f"Playwright not available: {str(e)}", "results": []}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            try:
                page.goto(self.BASE_URL, timeout=30000)
                
                # DEBUG
                print(f"[DEBUG-TJRJ] URL: {page.url}")
                print(f"[DEBUG-TJRJ] Title: {page.title()}")
                
                # Salvar HTML inicial para debug
                with open("debug_tjrj_initial.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                
                # Aguardar renderização do formulário (PJe)
                print("[DEBUG-TJRJ] Aguardando renderização do formulário PJe...")
                try:
                    # Espera pelo input de nome da parte ou processo
                    page.wait_for_selector(
                        "input[id*='nomeParte'], input[id*='numProcesso']",
                        timeout=20000
                    )
                except Exception as e:
                    print(f"[DEBUG-TJRJ] Timeout aguardando formulário: {e}")
                    print(f"[DEBUG-TJRJ] Conteúdo visível: {page.inner_text('body')[:500]}")

                # DEBUG: Listar todos os inputs visíveis para diagnóstico
                inputs = page.locator("input").all()
                print(f"[DEBUG-TJRJ] Total inputs encontrados: {len(inputs)}")
                for i, inp in enumerate(inputs):
                    try:
                        if inp.is_visible():
                            print(f"[DEBUG-TJRJ] Input {i}: id='{inp.get_attribute('id')}', name='{inp.get_attribute('name')}', placeholder='{inp.get_attribute('placeholder')}'")
                    except:
                        pass

                if self._is_process_number(query):
                    # Busca por CNJ
                    print("[DEBUG-TJRJ] Busca por CNJ")
                    # Seletor PJe para processo
                    # Ex: fPP:numProcesso-inputNumeroProcessoDecoration:numProcesso-inputNumeroProcesso
                    page.fill("input[id*='numProcesso'][type='text']", query)
                    page.click("input[value='Pesquisar'], button:has-text('Pesquisar')", timeout=5000)
                elif self.validate_input(query):
                    # Busca por Nome
                    print(f"[DEBUG-TJRJ] Busca por Nome: {query}")
                    
                    # Tentar encontrar campo de nome dinamicamente
                    nome_input_selector = None
                    possible_selectors = [
                        "input[id*='nomeParte']",
                        "input[name*='nomeParte']",
                        "input[id*='NomeParte']",
                        "input[label='Nome da Parte']"
                    ]
                    
                    for sel in possible_selectors:
                        if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                            nome_input_selector = sel
                            print(f"[DEBUG-TJRJ] Campo de nome encontrado: {sel}")
                            break
                    
                    if not nome_input_selector:
                        print("[DEBUG-TJRJ] Campo de nome NÃO encontrado pelos seletores padrão. Tentando estratégia de label...")
                        # Tentar achar pelo label
                        try:
                            label = page.locator("label:has-text('Parte'), label:has-text('Nome')").first
                            if label.is_visible():
                                id_alvo = label.get_attribute("for")
                                if id_alvo:
                                    nome_input_selector = f"input[id='{id_alvo}']"
                                    print(f"[DEBUG-TJRJ] Campo de nome encontrado via Label: {nome_input_selector}")
                        except:
                            pass

                    if nome_input_selector:
                        page.fill(nome_input_selector, query)
                        # Clicar em pesquisar
                        # Tentar ID específico primeiro (fPP:searchProcessos)
                        # Precisamos escapar o : para seletores CSS
                        if page.locator("#fPP\\:searchProcessos").is_visible():
                            print("[DEBUG-TJRJ] Clicando em #fPP:searchProcessos")
                            try:
                                page.screenshot(path="debug_tjrj_before_click.png")
                            except: pass
                            page.click("#fPP\\:searchProcessos")
                        else:
                            print("[DEBUG-TJRJ] Clicando em botão genérico de Pesquisar")
                            page.click("input[value='Pesquisar'], button:has-text('Pesquisar')")
                    else:
                        print("[DEBUG-TJRJ] ABORTANDO: Impossível localizar campo de nome.")
                        return {
                            "tribunal": "TJRJ",
                            "status": "error",
                            "msg": "Layout do TJRJ mudou ou campo de nome indisponível"
                        }
                
                # Esperar resultados
                try:
                    # PJe pode demorar e usa AJAX
                    print("[DEBUG-TJRJ] Aguardando resultados...")
                    
                    # 1. Esperar loader sumir (se aparecer)
                    try:
                        page.wait_for_selector(".ajax-loader", state="hidden", timeout=5000)
                    except:
                        pass

                    # 2. Esperar tabela ou mensagem de erro
                    # O tbody da tabela de resultados é fPP:processosTable:tb
                    # Mensagem de erro/aviso: .rich-messages-label ou .alert
                    try:
                        page.wait_for_selector(
                            "#fPP\\:processosTable\\:tb tr, .rich-messages-label, .alert-info, .rich-table-row", 
                            timeout=15000
                        )
                    except Exception as e:
                        print(f"[DEBUG-TJRJ] Timeout esperando seletor de resultado: {e}")
                    
                    # Dump HTML para debug
                    try:
                        with open("debug_tjrj_result_page.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        page.screenshot(path="debug_tjrj_after_search.png")
                    except: pass

                except Exception as e:
                    print(f"[DEBUG-TJRJ] Erro geral aguardando resultados: {e}")
                
                # DEBUG: Salvar HTML do resultado
                with open("debug_tjrj_result.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                # page.screenshot(path="debug_tjrj_result.png")
                
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                results = []
                
                # Extração PJe - Focada no ID da tabela
                # Tabela ID: fPP:processosTable
                tabela_resultados = soup.find("table", id="fPP:processosTable")
                if tabela_resultados:
                    tbody = tabela_resultados.find("tbody")
                    if tbody:
                        rows = tbody.find_all("tr")
                        print(f"[DEBUG-TJRJ] Linhas na tabela: {len(rows)}")
                        for row in rows:
                            # PJe rows usually have: Icon, Processo, ...
                            # Coluna Processo geralmente tem um link ou texto
                            texto_row = row.get_text(" ", strip=True)
                            
                            # Tentar extrair CNJ
                            match = re.search(r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", texto_row)
                            if match:
                                cnj = match.group(1)
                                results.append({
                                    "processo": cnj,
                                    "cnj": cnj,
                                    "tribunal": "TJRJ",
                                    "raw": texto_row[:200],
                                    "origem": "TJRJ-PJe",
                                    "situacao": "Encontrado"
                                })
                else:
                    # Fallback para busca genérica
                    print("[DEBUG-TJRJ] Tabela fPP:processosTable não encontrada, tentando fallback...")
                    tabelas = soup.find_all("table", class_="rich-table")
                
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
