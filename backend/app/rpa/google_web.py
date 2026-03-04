import logging
from playwright.sync_api import sync_playwright
import time
import random

class GoogleWebRPA:
    def search(self, query):
        results = []
        
        # Clean query just in case, but keep formatting for precision if needed
        # For CNJ, sometimes removing punctuation helps, sometimes quotes help.
        # Let's try both if one fails? For now, let's use the exact query.
        
        with sync_playwright() as p:
            # Launch browser with stealth args
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certificate-errors",
                    "--ignore-ssl-errors",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo"
            )
            
            # Stealth scripts
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = context.new_page()

            found_results = False

            # ---------------------------------------------------------
            # STRATEGY 1: DuckDuckGo HTML (No JS, fast, robust)
            # ---------------------------------------------------------
            try:
                print("DEBUG: Trying DuckDuckGo HTML...")
                # Try exact match first
                search_url = f"https://html.duckduckgo.com/html/?q=%22{query}%22+processo"
                page.goto(search_url, wait_until="load", timeout=15000)
                
                # Check for results
                if page.locator(".result__body").count() > 0:
                    print("DEBUG: DDG HTML found results.")
                    found_results = True
                    self._parse_ddg_html(page, results)
                else:
                    print("DEBUG: DDG HTML found no results.")
            except Exception as e:
                print(f"DEBUG: DDG HTML Error: {e}")

            # ---------------------------------------------------------
            # STRATEGY 2: Google (Stealth)
            # ---------------------------------------------------------
            if not found_results or len(results) == 0:
                try:
                    print("DEBUG: Trying Google...")
                    # Random delay
                    time.sleep(random.uniform(1, 2))
                    
                    search_url = f"https://www.google.com/search?q={query}+processo+jusbrasil+escavador&hl=pt-BR"
                    page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                    
                    # Handle Consent Popup (if any)
                    try:
                        accept_all = page.locator("button:has-text('Aceitar tudo'), button:has-text('Concordo')")
                        if accept_all.is_visible(timeout=2000):
                            accept_all.click()
                            time.sleep(1)
                    except:
                        pass

                    # Wait for results
                    try:
                        page.wait_for_selector("div.g", timeout=5000)
                    except:
                        pass
                    
                    if page.locator("div.g").count() > 0:
                         print("DEBUG: Google found results.")
                         found_results = True
                         self._parse_google(page, results)
                    else:
                         print("DEBUG: Google found no results or captcha.")
                         # Snapshot for debug if needed
                         # page.screenshot(path="google_debug.png")
                except Exception as e:
                    print(f"DEBUG: Google Error: {e}")

            browser.close()

        return {
            "status": "success",
            "results": results
        }

    def _parse_ddg_html(self, page, results):
        items = page.locator(".result__body")
        for i in range(min(items.count(), 5)):
            try:
                item = items.nth(i)
                link_el = item.locator("a.result__a").first
                snippet_el = item.locator("a.result__snippet").first
                
                if not link_el.count(): continue
                
                link = link_el.get_attribute("href")
                title = link_el.inner_text()
                snippet = snippet_el.inner_text() if snippet_el.count() else ""
                
                self._add_result(results, title, snippet, link)
            except Exception as e:
                print(f"Error parsing DDG item {i}: {e}")

    def _parse_google(self, page, results):
        items = page.locator("div.g")
        for i in range(min(items.count(), 5)):
            try:
                item = items.nth(i)
                link_el = item.locator("a").first
                title_el = item.locator("h3").first
                snippet_el = item.locator("div.VwiC3b, span.aCOpRe").first
                
                if not link_el.count(): continue
                
                link = link_el.get_attribute("href")
                title = title_el.inner_text() if title_el.count() else "Sem título"
                snippet = snippet_el.inner_text() if snippet_el.count() else ""
                
                self._add_result(results, title, snippet, link)
            except Exception as e:
                print(f"Error parsing Google item {i}: {e}")

    def _add_result(self, results, title, snippet, link):
        # Filter and Categorize
        source = "WEB"
        if "jusbrasil" in link: source = "JUSBRASIL"
        elif "escavador" in link: source = "ESCAVADOR"
        elif "projuris" in link: source = "PROJURIS"
        elif "tjpa.jus.br" in link: source = "TJPA"
        elif "jus.br" in link: source = "TRIBUNAL"
        elif "trf" in link: source = "TRF"
        
        print(f"DEBUG: Found {link} ({source})")
        
        # Accept broad range of relevant sources
        if source != "WEB" or "processo" in title.lower() or "autos" in title.lower() or "jus" in link:
            results.append({
                "classe": "Resultado Web",
                "assunto": title,
                "descricao": snippet,
                "raw": f"Fonte: {source} - {link}",
                "tribunal": "EXTERNO",
                "origem": source,
                "link": link
            })
