from typing import Dict, Any, List
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.parse import quote_plus
from urllib.request import urlopen, Request
# from playwright.sync_api import sync_playwright # Lazy import
import time
import re
import xml.etree.ElementTree as ET
from app.rpa.base import BaseRPA

class GoogleNewsRPA(BaseRPA):
    BASE_URL = "https://www.google.com/search?q={}&tbm=nws&start={}"
    
    # Lista básica de estados e capitais para inferência
    LOCATIONS = {
        "AC": ["ACRE", "RIO BRANCO", "CRUZEIRO DO SUL"],
        "AL": ["ALAGOAS", "MACEIO", "ARAPIRACA"],
        "AP": ["AMAPA", "MACAPA", "SANTANA"],
        "AM": ["AMAZONAS", "MANAUS", "PARINTINS"],
        "BA": ["BAHIA", "SALVADOR", "FEIRA DE SANTANA", "VITORIA DA CONQUISTA", "CAMACARI"],
        "CE": ["CEARA", "FORTALEZA", "CAUCAIA", "JUAZEIRO DO NORTE"],
        "DF": ["DISTRITO FEDERAL", "BRASILIA", "CEILANDIA", "TAGUATINGA"],
        "ES": ["ESPIRITO SANTO", "VITORIA", "VILA VELHA", "SERRA"],
        "GO": ["GOIAS", "GOIANIA", "APARECIDA DE GOIANIA", "ANAPOLIS"],
        "MA": ["MARANHAO", "SAO LUIS", "IMPERATRIZ"],
        "MT": ["MATO GROSSO", "CUIABA", "VARZEA GRANDE"],
        "MS": ["MATO GROSSO DO SUL", "CAMPO GRANDE", "DOURADOS"],
        "MG": ["MINAS GERAIS", "BELO HORIZONTE", "UBERLANDIA", "CONTAGEM", "JUIZ DE FORA", "BETIM"],
        "PA": ["PARÁ", "BELEM", "ANANINDEUA", "SANTAREM", "MARABA"], # Removido PARA sem acento
        "PB": ["PARAIBA", "JOAO PESSOA", "CAMPINA GRANDE"],
        "PR": ["PARANA", "CURITIBA", "LONDRINA", "MARINGA", "PONTA GROSSA"],
        "PE": ["PERNAMBUCO", "RECIFE", "JABOATAO", "OLINDA", "CARUARU"],
        "PI": ["PIAUI", "TERESINA", "PARNAIBA"],
        "RJ": ["RIO DE JANEIRO", "NITEROI", "SAO GONCALO", "DUQUE DE CAXIAS", "NOVA IGUACU"],
        "RN": ["RIO GRANDE DO NORTE", "NATAL", "MOSSORO"],
        "RS": ["RIO GRANDE DO SUL", "PORTO ALEGRE", "CAXIAS DO SUL", "CANOAS", "PELOTAS"],
        "RO": ["RONDONIA", "PORTO VELHO", "JI-PARANA"],
        "RR": ["RORAIMA", "BOA VISTA"],
        "SC": ["SANTA CATARINA", "FLORIANOPOLIS", "JOINVILLE", "BLUMENAU", "SAO JOSE"],
        "SP": ["SAO PAULO", "CAMPINAS", "GUARULHOS", "SOROCABA", "RIBEIRAO PRETO", "SANTOS", "SÃO PAULO", "OSASCO", "SAO BERNARDO"],
        "SE": ["SERGIPE", "ARACAJU", "NOSSA SENHORA DO SOCORRO"],
        "TO": ["TOCANTINS", "PALMAS", "ARAGUAINA"]
    }

    def _infer_location(self, text: str) -> Dict[str, str]:
        text_upper = text.upper()
        for uf, cities in self.LOCATIONS.items():
            for city in cities:
                if city in text_upper:
                    return {"city": city.title(), "state": uf}
        return {"city": None, "state": None}

    def search(self, query: str, max_pages: int = 1) -> Dict[str, Any]:
        results = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 720}
                )
                page = context.new_page()
                
                for page_num in range(max_pages):
                    start_index = page_num * 10
                    url = self.BASE_URL.format(query, start_index)
                    
                    try:
                        page.goto(url, timeout=30000)
                        
                        for selector in [
                            "button:has-text('Aceitar tudo')",
                            "button:has-text('Aceitar')",
                            "button:has-text('I agree')",
                            "button:has-text('Accept all')"
                        ]:
                            try:
                                page.click(selector, timeout=1500)
                                break
                            except Exception:
                                continue
                        page.wait_for_selector("body", timeout=10000)
                        
                        # Extract news items
                        articles = page.locator("div.SoaBEf, div.MjjYud, div.Gx5Zad, article").all()
                        if not articles:
                            articles = page.locator("a.WlydOe, a[jsname='UWckNb']").all()
                        
                        if not articles:
                            break

                        for article in articles:
                            try:
                                title_el = article.locator("div[role='heading'], h3").first
                                link_el = article.locator("a").first
                                is_link_node = False
                                if not title_el.count() and not link_el.count():
                                    title_el = article
                                    link_el = article
                                    is_link_node = True
                                
                                if not title_el.count() or not link_el.count():
                                    continue
                                    
                                title = title_el.inner_text()
                                link = link_el.get_attribute("href")
                                if is_link_node and not title:
                                    title = link_el.inner_text()
                                
                                source_el = article.locator(".CEMjEf, .NUnG9d, span").first
                                source = source_el.inner_text() if source_el.count() else "Desconhecido"
                                
                                snippet_el = article.locator(".GI74Re, .I26qU, .st").first
                                snippet = snippet_el.inner_text() if snippet_el.count() else ""
                                
                                date_el = article.locator(".OSrXXb, span").last
                                date_val = date_el.inner_text() if date_el.count() else ""
                                
                                img_el = article.locator("img").first
                                image_url = None
                                if img_el.count():
                                    src = img_el.get_attribute("src")
                                    srcset = img_el.get_attribute("srcset")
                                    
                                    # Tenta pegar a melhor imagem do srcset ou src
                                    if srcset:
                                        try:
                                            # Pega a última URL do srcset (geralmente a maior)
                                            image_url = srcset.split(",")[-1].strip().split(" ")[0]
                                        except:
                                            image_url = src
                                    else:
                                        image_url = src

                                    # Tenta limpar URL do Google para alta resolução
                                    if image_url and "googleusercontent.com" in image_url:
                                        try:
                                            # Remove parâmetros de redimensionamento para pegar original
                                            # Ex: url=...-w200-h200... -> url=...-s0 (full size) ou remover params
                                            # A estratégia comum é remover tudo após o '=' e adicionar s0 ou w1000
                                            base_url = image_url.split("=")[0]
                                            image_url = base_url + "=w800-h600-c" # Força tamanho maior
                                        except:
                                            pass

                                
                                # Inferir localização
                                loc = self._infer_location(f"{title} {snippet}")
                                
                                if link and title and link.startswith("http"):
                                    results.append({
                                        "title": title,
                                        "url": link,
                                        "source": source,
                                        "snippet": snippet,
                                        "published_date": date_val,
                                        "image_url": image_url,
                                        "city": loc["city"],
                                        "state": loc["state"]
                                    })
                            except Exception as e:
                                continue 
                        
                        # Random delay between pages
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"Error on page {page_num}: {e}")
                        break
                
                browser.close()

                if not results:
                    results = self._search_rss(query, max_items=max_pages * 25)
                results = self._dedupe_results(results)
                return {
                    "source": "Google News",
                    "status": "success",
                    "query": query,
                    "results": results
                }

        except Exception as e:
            fallback_results = self._search_rss(query, max_items=max_pages * 25)
            if fallback_results:
                return {
                    "source": "Google News",
                    "status": "success",
                    "query": query,
                    "results": self._dedupe_results(fallback_results)
                }
            return {
                "source": "Google News",
                "status": "error",
                "error": str(e)
            }

    def _extract_real_url(self, google_url: str) -> str:
        """Extrai a URL real de um link do Google News"""
        if not google_url:
            return ""
        try:
            if "news.google.com" in google_url:
                parsed = urlsplit(google_url)
                params = dict(parse_qsl(parsed.query))
                if "url" in params:
                    return params["url"]
            return google_url
        except Exception:
            return google_url

    def _search_rss(self, query: str, max_items: int = 25) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=20) as response:
                payload = response.read()
            root = ET.fromstring(payload)
            channel = root.find("channel")
            if channel is None:
                return items
            for node in channel.findall("item")[:max_items]:
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                description = (node.findtext("description") or "").strip()
                pub_date = (node.findtext("pubDate") or "").strip()
                source = "Google News"
                source_node = node.find("{http://search.yahoo.com/mrss/}source")
                if source_node is not None and source_node.text:
                    source = source_node.text.strip()
                clean_title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
                snippet = re.sub(r"<[^>]+>", " ", description)
                snippet = re.sub(r"\s+", " ", snippet).strip()
                loc = self._infer_location(f"{clean_title} {snippet}")
                
                real_url = self._extract_real_url(link)
                
                if clean_title and real_url:
                    items.append({
                        "title": clean_title,
                        "url": real_url,
                        "source": source,
                        "snippet": snippet,
                        "published_date": pub_date,
                        "image_url": None,
                        "city": loc["city"],
                        "state": loc["state"]
                    })
        except Exception:
            return items
        return items

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parts = urlsplit(url.strip())
            query_items = [
                (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "igshid", "mc_cid", "mc_eid"}
            ]
            query = urlencode(query_items, doseq=True)
            return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), query, ""))
        except Exception:
            return url.strip()

    def _dedupe_results(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique_items = []
        for item in items:
            url = self._normalize_url(item.get("url", ""))
            if url:
                item["url"] = url
            title = str(item.get("title") or "").strip().lower()
            source = str(item.get("source") or "").strip().lower()
            date_val = str(item.get("published_date") or "").strip().lower()
            key = f"{url or title}|{source}|{date_val}"
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)
        return unique_items
