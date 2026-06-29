from typing import Dict, Any, List
import re
import time
from .base_system import BaseSystemRPA
from bs4 import BeautifulSoup

class ESajRPA(BaseSystemRPA):
    """
    Implementação genérica para tribunais que utilizam o sistema e-SAJ (SP, SC, AC, AL, AM, MS).
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
                page.goto(self.base_url, timeout=45000)
                
                # Identificar tipo de busca
                clean_query = re.sub(r"\D", "", query)
                
                if len(clean_query) == 20:
                    # Selecionar busca por número do processo (Garantir radio UNIFICADO)
                    try:
                        page.locator("input[id='radioNumeroUnificado']").click()
                    except:
                        pass
                    
                    # Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OR
                    # Campo 1: NNNNNNN-DD.AAAA (13 dígitos numéricos)
                    num_digito_ano = clean_query[:13]
                    # Campo 2: OR (4 dígitos finais)
                    foro = clean_query[16:]
                    
                    page.locator("input[id='numeroDigitoAnoUnificado']").fill(num_digito_ano)
                    page.locator("input[id='foroNumeroUnificado']").fill(foro)
                    page.click("input[id='botaoConsultarProcessos']")
                else:
                    # Busca por Nome - Tentar ser resiliente
                    # Alguns tribunais pedem 'Nome da Parte' explicitamente no select
                    
                    # 1. Tentar selecionar "Nome da Parte" se o select existir
                    try:
                        select_pesquisa = page.locator("select[id='cbPesquisa']")
                        if select_pesquisa.count() > 0:
                            # Tentar selecionar pelo Value primeiro (mais seguro)
                            try:
                                select_pesquisa.select_option(value="NMPARTE")
                                # Esperar input aparecer
                                page.wait_for_selector("#campo_NMPARTE", timeout=5000)
                            except:
                                try:
                                    select_pesquisa.select_option(label="Nome da Parte") # Tentar label exata
                                except:
                                    try:
                                        select_pesquisa.select_option(label="Nome da parte") # Tentar label com minúscula
                                    except:
                                        pass # Deixar padrão se falhar
                    except Exception as e:
                        pass

                    # 2. Preencher campo de busca
                    # O ID pode variar: 'campo_NMPARTE', 'nmParte', 'campo_JD', etc.
                    # Vamos tentar os mais comuns
                    input_filled = False
                    for selector in ["input[id='campo_NMPARTE']", "input[name='nmParte']", "#campo_NMPARTE", "#nmParte"]:
                        try:
                            if page.locator(selector).count() > 0:
                                if not page.locator(selector).is_visible():
                                     pass
                                page.locator(selector).fill(query)
                                input_filled = True
                                break
                        except:
                            continue
                    
                    if not input_filled:
                         # Fallback perigoso: preencher o primeiro input text visível grande
                         inputs = page.locator("input[type='text']")
                         for i in range(inputs.count()):
                             if inputs.nth(i).is_visible():
                                 inputs.nth(i).fill(query)
                                 break

                    # 3. Clicar em consultar
                try:
                    btn = page.locator("input[id='botaoConsultarProcessos']")
                    if btn.is_visible():
                        print("DEBUG: Clicking 'Consultar Processos'")
                        btn.click()
                    else:
                        print("DEBUG: 'Consultar Processos' button not visible, pressing Enter")
                        page.keyboard.press("Enter")
                except Exception as e:
                    print(f"DEBUG: Error clicking search button: {e}")
                    page.keyboard.press("Enter")

                # Esperar resultados
                try:
                    print("DEBUG: Waiting for results...")
                    # Se houver apenas 1 resultado, o TJSP redireciona direto para a página do processo (#labelProcessoUnico ou #numeroProcesso)
                    page.wait_for_selector(
                        "#tabelaResultados, #livre, .mensagemErro, #mensagemRetorno, .modal-content, #labelProcessoUnico, .headerProcesso, #numeroProcesso, #tabelaPartesPrincipais, input[type='radio']", 
                        timeout=30000
                    )
                    print("DEBUG: Result selector found!")
                except Exception as e:
                    print(f"DEBUG: Timeout waiting for results. URL: {page.url}")
                    # Screenshot for debug (saved locally)
                    page.screenshot(path="esaj_timeout.png")
                    return {"tribunal": self.tribunal_name, "status": "timeout", "results": [], "msg": "Timeout aguardando resposta"}

                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Verificar mensagem de retorno (erro ou aviso)
                msg_retorno = soup.find(id="mensagemRetorno")
                if msg_retorno:
                    msg_text = msg_retorno.get_text(strip=True)
                    if msg_text:
                        if not soup.find(id="tabelaResultados") and not soup.find(id="numeroProcesso"):
                             return {
                                "tribunal": self.tribunal_name,
                                "status": "warning",
                                "query": query,
                                "results": [],
                                "msg": msg_text
                            }

                # Parsear resultados
                results = []
                
                # Caso 1: Lista de Processos (tabelaResultados)
                # Mesmo com mensagem de aviso, pode haver uma tabela parcial
                table = soup.find(id="tabelaResultados")
                if table:
                    # Rows da tabela (geralmente tem id ou class específica, mas vamos iterar trs)
                    # O header costuma ser thead ou primeira tr th
                    rows = table.find_all("tr", class_=['fundoClaro', 'fundoEscuro'])
                    
                    # Se não achar por classe, tenta todos trs exceto header
                    if not rows:
                        all_rows = table.find_all("tr")
                        rows = [r for r in all_rows if not r.find("th")]

                    for row in rows:
                        cols = row.find_all("td")
                        
                        if len(cols) >= 2:
                            # A estrutura pode variar:
                            # Col 1: Checkbox (as vezes)
                            # Col 2: Número do Processo e Link (nuProcesso)
                            # Col 3: Foro / Vara / Classe
                            
                            # Tentar achar link com classe "linkProcesso" ou qualquer link na célula
                            proc_link = row.find("a", class_="linkProcesso")
                            if not proc_link:
                                # Tenta procurar em qualquer coluna
                                for col in cols:
                                    link = col.find("a", href=True)
                                    if link and "processo" in link.get("href", ""):
                                        proc_link = link
                                        break
                            
                            if proc_link:
                                proc_text = proc_link.get_text(strip=True)
                                proc_href = proc_link.get("href")
                                
                                # Tentar extrair mais dados das colunas
                                details = []
                                for col in cols:
                                    txt = col.get_text(" ", strip=True)
                                    if txt and txt != proc_text:
                                        details.append(txt)
                                
                                desc = " | ".join(details)
                                
                                results.append({
                                    "processo": proc_text,
                                    "cnj": re.sub(r"\D", "", proc_text), # Clean CNJ
                                    "descricao": desc,
                                    "link": f"{self.base_url.replace('/open.do', '')}{proc_href}" if proc_href.startswith("/") else proc_href,
                                    "origem": f"{self.tribunal_name} (e-SAJ)"
                                })

                # Caso 2: Processo Único (Redirecionamento direto)
                # Verifica se estamos na página de detalhes
                elif soup.find(id="numeroProcesso") or soup.find("span", id="labelProcessoUnico"):
                    # Extrair dados da página de detalhe
                    proc_num = soup.find(id="numeroProcesso")
                    if proc_num:
                        proc_text = proc_num.get_text(strip=True)
                    elif soup.find("span", id="labelProcessoUnico"):
                        proc_text = soup.find("span", id="labelProcessoUnico").get_text(strip=True)
                    else:
                        proc_text = "N/A"
                    
                    # Extrair classe, assunto, foro
                    classe_elem = soup.find(id="classeProcesso")
                    assunto_elem = soup.find(id="assuntoProcesso")
                    foro_elem = soup.find(id="foroProcesso")
                    vara_elem = soup.find(id="varaProcesso")
                    
                    classe_val = classe_elem.get_text(strip=True) if classe_elem else ""
                    assunto_val = assunto_elem.get_text(strip=True) if assunto_elem else ""
                    foro_val = foro_elem.get_text(strip=True) if foro_elem else ""
                    
                    # Extrair partes (modificado para objetos)
                    partes = []
                    table_partes = soup.find(id="tablePartesPrincipais")
                    if table_partes:
                        for row in table_partes.find_all("tr"):
                            cols_p = row.find_all("td")
                            if len(cols_p) >= 2:
                                tipo_parte = cols_p[0].get_text(strip=True).replace(":", "").strip()
                                nome_parte = cols_p[1].get_text(" ", strip=True)
                                partes.append({"tipo": tipo_parte, "nome": nome_parte})

                    results.append({
                        "processo": proc_text,
                        "cnj": re.sub(r"\D", "", proc_text),
                        "classe": classe_val,
                        "assunto": assunto_val,
                        "foro": foro_val,
                        "descricao": f"{classe_val} - {assunto_val} - {foro_val}",
                        "partes": partes,
                        "origem": f"{self.tribunal_name} (e-SAJ Único)"
                    })

                else:
                    # Debug: Salvar HTML se não achou nada conhecido
                    print(f"DEBUG: Unknown layout for {query}")
                    with open(f"esaj_debug_{re.sub(r'[^a-zA-Z0-9]', '_', query)}.html", "w", encoding="utf-8") as f:
                        f.write(soup.prettify())
                
                return {
                    "tribunal": self.tribunal_name,
                    "status": "success",
                    "found": len(results) > 0,
                    "query": query,
                    "results": results,
                    "msg": f"Encontrados {len(results)} processos" if results else "Nenhum processo identificado ou layout desconhecido"
                }

            except Exception as e:
                return {
                    "tribunal": self.tribunal_name,
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
