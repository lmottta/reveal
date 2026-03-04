import re
from typing import Dict, Any, List
# from playwright.sync_api import sync_playwright # Lazy import inside methods
from .base import BaseRPA
from bs4 import BeautifulSoup

class TJSPRPA(BaseRPA):
    """
    Implementação de RPA para o Tribunal de Justiça de São Paulo (e-SAJ).
    Utiliza Playwright para interação real.
    """
    
    BASE_URL = "https://esaj.tjsp.jus.br/cpopg/open.do"

    def _is_process_number(self, query: str) -> bool:
        # Regex básico para CNJ: NNNNNNN-DD.AAAA.J.TR.OR
        # Ou apenas números (20 dígitos)
        clean_query = re.sub(r"\D", "", query)
        return len(clean_query) == 20 or bool(re.match(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", query))

    def search(self, query: str) -> Dict[str, Any]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            return {"error": f"Playwright not available: {str(e)}", "results": []}

        with sync_playwright() as p:
            # Launch browser (headless=True para produção, False para debug se necessário)
            # Como estamos em ambiente sem display gráfico fácil, headless=True é mandatório
            # Adicionar user_agent real para evitar bloqueios simples
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            try:
                page.goto(self.BASE_URL, timeout=45000)
                
                # Identificar tipo de busca
                if self._is_process_number(query):
                    # Selecionar busca por número do processo (Garantir radio UNIFICADO)
                    try:
                        page.locator("input[id='radioNumeroUnificado']").click()
                    except:
                        pass

                    # Limpar query para apenas números
                    clean_query = re.sub(r"\D", "", query)
                    
                    if len(clean_query) == 20:
                        # Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OR
                        # Campo 1: NNNNNNN-DD.AAAA (13 dígitos numéricos)
                        num_digito_ano = clean_query[:13]
                        # Campo 2: OR (4 dígitos finais)
                        foro = clean_query[16:]
                        
                        # O campo JTR (8.26) geralmente é fixo ou preenchido automaticamente, 
                        # mas vamos focar nos campos principais
                        
                        page.locator("input[id='numeroDigitoAnoUnificado']").fill(num_digito_ano)
                        page.locator("input[id='foroNumeroUnificado']").fill(foro)
                    else:
                        # Tentar preencher direto se for outro formato ou deixar usuário corrigir
                        # Mas o ID 'processoMascarado' não existe mais. Tentar 'numeroDigitoAnoUnificado'
                        page.locator("input[id='numeroDigitoAnoUnificado']").fill(query)

                    page.click("input[id='botaoConsultarProcessos']")
                else:
                    # Busca por Nome - Tentar ser resiliente
                    # Alguns tribunais pedem 'Nome da Parte' explicitamente no select
                    
                    # 1. Tentar selecionar "Nome da Parte" se o select existir
                    # O ID 'cbPesquisa' é comum no SAJ/SG
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
                        print(f"Erro ao selecionar tipo de pesquisa: {e}")

                    # 2. Preencher campo de busca
                    # O ID pode variar: 'campo_NMPARTE', 'nmParte', 'campo_JD', etc.
                    # Vamos tentar os mais comuns
                    input_filled = False
                    # Adicionar wait_for_selector para garantir visibilidade
                    for selector in ["input[id='campo_NMPARTE']", "input[name='nmParte']", "#campo_NMPARTE", "#nmParte"]:
                        try:
                            if page.locator(selector).count() > 0:
                                if not page.locator(selector).is_visible():
                                     # Tentar forçar visibilidade se necessário ou esperar
                                     pass
                                page.locator(selector).fill(query)
                                input_filled = True
                                print(f"DEBUG: Campo de busca preenchido: {selector} com valor '{query}'")
                                break
                        except:
                            continue
                    
                    if not input_filled:
                         print("DEBUG: Nenhum campo específico encontrado, tentando fallback...")
                         # Fallback perigoso: preencher o primeiro input text visível grande
                         inputs = page.locator("input[type='text']")
                         for i in range(inputs.count()):
                             if inputs.nth(i).is_visible():
                                 inputs.nth(i).fill(query)
                                 break

                    # 3. Clicar em consultar
                    # Tentar disparar o evento de click e também ENTER para garantir
                    try:
                        btn = page.locator("input[id='botaoConsultarProcessos']")
                        if btn.is_visible():
                            btn.click()
                        else:
                            page.keyboard.press("Enter")
                    except Exception as e:
                        print(f"Erro ao clicar: {e}")
                        page.keyboard.press("Enter")

                # Esperar resultados
                # Seletor de erro, tabela, mensagem de retorno, captcha OU PROCESSO UNICO
                try:
                    # Se houver apenas 1 resultado, o TJSP redireciona direto para a página do processo (#labelProcessoUnico ou #numeroProcesso)
                    page.wait_for_selector(
                        "#tabelaResultados, #livre, .mensagemErro, #mensagemRetorno, .modal-content, #labelProcessoUnico, .headerProcesso, #numeroProcesso, #tabelaPartesPrincipais", 
                        timeout=60000
                    )
                except Exception as e:
                    # Debug: Salvar HTML para análise
                    with open("debug_tjsp_error.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    
                    # Tentar tirar screenshot se possível (headless)
                    try:
                        page.screenshot(path="debug_tjsp_error.png")
                    except:
                        pass
                        
                    return {"tribunal": "TJSP", "status": "timeout", "results": [], "debug_msg": "Timeout aguardando resposta do TJSP. Verifique debug_tjsp_error.html"}

                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Verificar mensagem de retorno (erro ou aviso)
                msg_retorno = soup.find(id="mensagemRetorno")
                if msg_retorno:
                    msg_text = msg_retorno.get_text(strip=True)
                    if msg_text:
                        print(f"DEBUG: Mensagem de retorno encontrada: {msg_text}")
                        # Se não houver tabela de resultados, é um erro bloqueante da busca
                        if not soup.find(id="tabelaResultados") and not soup.find(id="numeroProcesso"):
                             return {
                                "tribunal": "TJSP",
                                "status": "warning",
                                "query": query,
                                "results": [],
                                "msg": msg_text
                            }

                # Parsear resultados
                results = []
                
                # Caso 1: Lista de Processos
                table = soup.find(id="tabelaResultados")
                if table:
                    # Rows com classe 'fundoClaro' e 'fundoEscuro'
                    rows = table.find_all("tr", class_=['fundoClaro', 'fundoEscuro'])
                    print(f"DEBUG: Encontradas {len(rows)} linhas na tabela de resultados.")
                    
                    for row in rows:
                        cols = row.find_all("td")
                        # Estrutura esperada:
                        # 0: Processo (com link)
                        # 1: Foro
                        # 2: Vara
                        # 3: Data Distr.
                        
                        if len(cols) >= 2:
                            proc_link = cols[0].find("a")
                            if proc_link:
                                proc_text = proc_link.get_text(strip=True)
                                proc_href = proc_link.get("href")
                                
                                # Detalhes na segunda linha (classe 'espaco-linha')? 
                                # No TJSP, as vezes o resumo está na mesma linha ou em div.
                                # Vamos pegar o texto da coluna 1 como Foro/Vara
                                foro_vara = cols[1].get_text(strip=True)
                                
                                results.append({
                                    "processo": proc_text,
                                    "descricao": foro_vara,
                                    "link": f"https://esaj.tjsp.jus.br{proc_href}",
                                    "origem": "TJSP 1º Grau"
                                })

                # Caso 2: Processo Único (Redirecionamento direto)
                # Verifica se estamos na página de detalhes
                elif soup.find(id="numeroProcesso") or soup.find("span", id="labelProcessoUnico"):
                    print("DEBUG: Redirecionado para processo único.")
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
                    vara_val = vara_elem.get_text(strip=True) if vara_elem else ""
                    
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
                        "classe": classe_val,
                        "assunto": assunto_val,
                        "foro": foro_val,
                        "vara": vara_val,
                        "descricao": f"{classe_val} - {assunto_val} - {foro_val}",
                        "partes": partes,
                        "origem": "TJSP 1º Grau (Único)"
                    })

                if not results:
                    print("DEBUG: Nenhum resultado encontrado no parser.")
                    with open("debug_tjsp_empty.html", "w", encoding="utf-8") as f:
                        f.write(page.content())

                return {
                    "tribunal": "TJSP",
                    "status": "success",
                    "query": query,
                    "results": results
                }

            except Exception as e:
                return {
                    "tribunal": "TJSP",
                    "status": "error",
                    "error": str(e)
                }
            finally:
                browser.close()
