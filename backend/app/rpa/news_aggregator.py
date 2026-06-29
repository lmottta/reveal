from typing import Dict, Any, List, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import time
import re
import xml.etree.ElementTree as ET
import random

class NewsAggregatorRPA:
    """
    Agregador de notícias de múltiplas fontes nacionais brasileiras.
    Foco em crimes sexuais e violência.
    """
    
    BASE_KEYWORDS = [
        "exploração sexual", "abuso sexual", "estupro", "violência sexual",
        "tráfico sexual", "pornografia infantil", "pedofilia", "aliciamento",
        "assedio sexual", "importunação sexual", "crime sexual"
    ]
    
    NEWS_SOURCES = {
        "g1": {
            "name": "G1",
            "rss": "https://g1.globo.com/rss/g1/",
            "search": "https://g1.globo.com/busca/?q={}",
            "enabled": True
        },
        "uol": {
            "name": "UOL",
            "rss": "https://noticias.uol.com.br/feed/",
            "search": "https://www.uol.com.br/search?q={}",
            "enabled": True
        },
        "terra": {
            "name": "Terra",
            "rss": "https://www.terra.com.br/rss/",
            "search": "https://www.terra.com.br/busca/{}",
            "enabled": True
        },
        "folha": {
            "name": "Folha de S.Paulo",
            "rss": "https://www.folha.uol.com.br/feed.xml",
            "search": "https://busca.folha.uol.com.br/search?q={}",
            "enabled": True
        },
        "r7": {
            "name": "R7",
            "rss": "https://www.r7.com/feed/rss/",
            "search": "https://www.r7.com/busca?term={}",
            "enabled": True
        },
        "band": {
            "name": "Band",
            "rss": None,
            "search": "https://www.band.uol.com.br/busca?q={}",
            "enabled": True
        },
        "estadao": {
            "name": "Estadão",
            "rss": "https://www.estadao.com.br/feed/rss/",
            "search": "https://www.estadao.com.br/busca?q={}",
            "enabled": True
        },
        "oglobo": {
            "name": "O Globo",
            "rss": "https://oglobo.globo.com/rss/feed/",
            "search": "https://oglobo.globo.com/busca/{}",
            "enabled": True
        },
        "correio": {
            "name": "Correio Braziliense",
            "rss": "https://www.correiobraziliense.com.br/rss/",
            "search": "https://www.correiobraziliense.com.br/busca?term={}",
            "enabled": True
        },
        "gazeta": {
            "name": "Gazeta do Povo",
            "rss": "https://www.gazetadopovo.com.br/feed/rss/",
            "search": "https://www.gazetadopovo.com.br/busca/?q={}",
            "enabled": True
        },
        "cnn": {
            "name": "CNN Brasil",
            "rss": "https://www.cnnbrasil.com.br/feed/",
            "search": "https://www.cnnbrasil.com.br/?s={}",
            "enabled": True
        },
        "metropoles": {
            "name": "Metrópoles",
            "rss": "https://www.metropoles.com.br/feed/",
            "search": "https://www.metropoles.com/busca?q={}",
            "enabled": True
        }
    }
    
    STATE_UF = [
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
        "RS", "RO", "RR", "SC", "SP", "SE", "TO"
    ]
    
    MAJOR_CITIES = [
        "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Brasília", "Salvador",
        "Fortaleza", "Recife", "Curitiba", "Porto Alegre", "Manaus",
        "Goiânia", "Campinas", "São Luís", "Natal", "João Pessoa",
        "Teresina", "Santo André", "São Bernardo do Campo", "Osasco",
        "São José dos Campos", "Ribeirão Preto", "Jaboatão dos Guararapes",
        "Contagem", "Duque de Caxias", "Nova Iguaçu", "São Gonçalo",
        "Niterói", "Belford Roxo", "Campinas", "Santo André", "São José dos Campos"
    ]

    def __init__(self):
        self.results = []
        
    def _extract_real_url(self, url: str) -> str:
        """Extrai a URL real de um link do Google News ou similar"""
        if not url:
            return ""
        try:
            if "news.google.com" in url:
                parsed = urlsplit(url)
                params = dict(parse_qsl(parsed.query))
                if "url" in params:
                    return params["url"]
            return url
        except Exception:
            return url
    
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
            path = parts.path.rstrip("/")
            return urlunsplit((parts.scheme, parts.netloc, path, query, "")).lower()
        except Exception:
            return url.strip().lower()
    
    def _infer_location(self, text: str) -> Dict[str, Optional[str]]:
        text_upper = text.upper()
        
        for uf in self.STATE_UF:
            if f" {uf} " in text_upper or f"({uf})" in text_upper:
                return {"state": uf, "city": None}
        
        city_state_map = {
            "SÃO PAULO": "SP", "CAMPINAS": "SP", "SANTOS": "SP", "RIBEIRÃO": "SP",
            "SOROCABA": "SP", "GUARULHOS": "SP", "OSASCO": "SP",
            "RIO DE JANEIRO": "RJ", "NITERÓI": "RJ", "SÃO GONÇALO": "RJ",
            "BELO HORIZONTE": "MG", "UBERLÂNDIA": "MG", "CONTAGEM": "MG",
            "CURITIBA": "PR", "LONDRINA": "PR", "MARINGÁ": "PR",
            "PORTO ALEGRE": "RS", "CAXIAS DO SUL": "RS",
            "FLORIANÓPOLIS": "SC", "JOINVILLE": "SC", "BLUMENAU": "SC",
            "BRASÍLIA": "DF", "TAGUATINGA": "DF",
            "GOIÂNIA": "GO", "ANÁPOLIS": "GO",
            "SALVADOR": "BA", "FEIRA DE SANTANA": "BA", "VITÓRIA DA CONQUISTA": "BA",
            "RECIFE": "PE", "JABOATÃO": "PE", "OLINDA": "PE", "CARUARU": "PE",
            "FORTALEZA": "CE", "CAUCAIA": "CE", "JUAZEIRO": "CE",
            "NATAL": "RN", "MOSSORÓ": "RN",
            "JOÃO PESSOA": "PB", "CAMPINA GRANDE": "PB",
            "MACEIÓ": "AL", "ARAPIRACA": "AL",
            "TERESINA": "PI", "PARNAÍBA": "PI",
            "SÃO LUÍS": "MA", "IMPERATRIZ": "MA",
            "BELÉM": "PA", "ANANINDEUA": "PA", "SANTARÉM": "PA",
            "MANAUS": "AM", "PARINTINS": "AM",
            "CUIABÁ": "MT", "VÁRZEA GRANDE": "MT",
            "CAMPO GRANDE": "MS", "DOURADOS": "MS",
            "VITÓRIA": "ES", "VILA VELHA": "ES", "SERRA": "ES",
            "ARACAJU": "SE", "NOSSA SENHORA DO SOCORRO": "SE",
            "PALMAS": "TO", "ARAGUAÍNA": "TO"
        }
        
        for city, state in city_state_map.items():
            if city in text_upper:
                return {"state": state, "city": city.title()}
        
        return {"state": None, "city": None}
    
    def _is_relevant(self, text: str) -> bool:
        text_upper = text.upper()
        keywords = [
            "SEXUAL", "ESTUPRO", "ABUSO", "PEDOFILIA", "PORNOGRAFIA",
            "TRAFICO", "VIOLENCIA", "ALICIAMENTO", "ASSEDIO", "IMPORTUNAÇÃO",
            "EXPLORAÇÃO", "VULNERÁVEL", "INCAPAZ", "MENOR", "INFANTIL"
        ]
        return any(kw in text_upper for kw in keywords)
    
    def _fetch_rss(self, rss_url: str, source_name: str, max_items: int = 20) -> List[Dict]:
        items = []
        try:
            request = Request(rss_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urlopen(request, timeout=15) as response:
                payload = response.read()
            
            root = ET.fromstring(payload)
            
            for node in root.findall(".//item")[:max_items]:
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                description = (node.findtext("description") or "").strip()
                pub_date = (node.findtext("pubDate") or "").strip()
                
                if not title or not link:
                    continue
                
                snippet = re.sub(r"<[^>]+>", " ", description)
                snippet = re.sub(r"\s+", " ", snippet).strip()[:300]
                
                full_text = f"{title} {snippet}"
                
                if self._is_relevant(full_text):
                    loc = self._infer_location(full_text)
                    real_url = self._extract_real_url(link)
                    items.append({
                        "title": title,
                        "url": real_url,
                        "source": source_name,
                        "snippet": snippet,
                        "published_date": pub_date,
                        "image_url": None,
                        "city": loc.get("city"),
                        "state": loc.get("state")
                    })
                    
        except Exception as e:
            print(f"  RSS Error ({source_name}): {e}")
        
        return items
    
    def _fetch_google_news_rss(self, query: str, max_items: int = 30) -> List[Dict]:
        items = []
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        
        try:
            request = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
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
                snippet = re.sub(r"\s+", " ", snippet).strip()[:300]
                
                full_text = f"{clean_title} {snippet}"
                
                if self._is_relevant(full_text):
                    loc = self._infer_location(full_text)
                    real_url = self._extract_real_url(link)
                    items.append({
                        "title": clean_title,
                        "url": real_url,
                        "source": source,
                        "snippet": snippet,
                        "published_date": pub_date,
                        "image_url": None,
                        "city": loc.get("city"),
                        "state": loc.get("state")
                    })
                    
        except Exception as e:
            print(f"  Google RSS Error for '{query}': {e}")
        
        return items
    
    def _dedupe_results(self, items: List[Dict]) -> List[Dict]:
        seen = set()
        unique_items = []
        
        for item in items:
            url = self._normalize_url(item.get("url", ""))
            if not url:
                continue
                
            title = str(item.get("title") or "").strip().lower()
            source = str(item.get("source") or "").strip().lower()
            date_val = str(item.get("published_date") or "").strip().lower()
            
            key = f"{url}|{title[:50]}"
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)
        
        return unique_items
    
    def search(self, query: str, max_pages: int = 3, sources: List[str] = None) -> Dict[str, Any]:
        """
        Executa busca agregada de notícias.
        
        Args:
            query: Termo de busca
            max_pages: Número máximo de páginas por fonte (para compatibilidade)
            sources: Lista de fontes específicas (None = todas)
        """
        results = []
        sources_to_use = sources if sources else [k for k, v in self.NEWS_SOURCES.items() if v.get("enabled")]
        
        print(f"NewsAggregator: Searching for '{query}'")
        print(f"Sources enabled: {', '.join(sources_to_use)}")
        
        for source_key in sources_to_use:
            source_info = self.NEWS_SOURCES.get(source_key)
            if not source_info:
                continue
            
            source_name = source_info["name"]
            rss_url = source_info.get("rss")
            
            if rss_url:
                print(f"  Fetching from {source_name} RSS...")
                items = self._fetch_rss(rss_url, source_name, max_items=25)
                results.extend(items)
                time.sleep(random.uniform(0.5, 1.5))
        
        print(f"  Total from RSS feeds: {len(results)}")
        
        search_queries = [query]
        for keyword in self.BASE_KEYWORDS[:5]:
            if keyword.lower() not in query.lower():
                search_queries.append(f"{query} {keyword}")
        
        for uf in self.STATE_UF:
            search_queries.append(f"{query} {uf}")
        
        for city in self.MAJOR_CITIES[:15]:
            search_queries.append(f"{query} {city}")
        
        random.shuffle(search_queries)
        search_queries = search_queries[:max_pages * 10]
        
        print(f"  Performing {len(search_queries)} Google News searches...")
        for search_term in search_queries:
            items = self._fetch_google_news_rss(search_term, max_items=15)
            results.extend(items)
            time.sleep(random.uniform(1, 2))
        
        results = self._dedupe_results(results)
        
        return {
            "source": "NewsAggregator",
            "status": "success",
            "query": query,
            "results": results
        }
    
    def collect_national(self, terms: List[str] = None, items_per_term: int = 30) -> Dict[str, Any]:
        """
        Coleta nacional de notícias sobre crimes sexuais.
        """
        if terms is None:
            terms = self.BASE_KEYWORDS
        
        results = []
        
        print(f"National Collection: {len(terms)} terms")
        
        for term in terms:
            print(f"  Collecting: {term}")
            
            result = self.search(term, max_pages=2)
            results.extend(result.get("results", []))
            
            time.sleep(random.uniform(1, 3))
        
        results = self._dedupe_results(results)
        
        return {
            "source": "NewsAggregator",
            "status": "success",
            "total_collected": len(results),
            "results": results
        }


class MultiPortalNewsRPA:
    """
    RPA para coleta de notícias de múltiplos portais brasileiros.
    Versão alternativa com foco em portais regionais e nacionais.
    """
    
    PORTALS = [
        {
            "name": "G1 - Portal de Notícias",
            "base_url": "https://g1.globo.com",
            "rss_feeds": [
                "https://g1.globo.com/rss/g1/",
                "https://g1.globo.com/sp/sao-paulo/rss/",
                "https://g1.globo.com/rj/rio-de-janeiro/rss/",
                "https://g1.globo.com/mg/minas-gerais/rss/",
                "https://g1.globo.com/pe/pernambuco/rss/",
                "https://g1.globo.com/ba/bahia/rss/",
                "https://g1.globo.com/ce/ceara/rss/",
                "https://g1.globo.com/pr/parana/rss/",
                "https://g1.globo.com/rs/rio-grande-do-sul/rss/",
                "https://g1.globo.com/df/distrito-federal/rss/"
            ]
        },
        {
            "name": "UOL - Notícias",
            "base_url": "https://noticias.uol.com.br",
            "rss_feeds": [
                "https://noticias.uol.com.br/feed/"
            ]
        },
        {
            "name": "Terra - Notícias",
            "base_url": "https://www.terra.com.br",
            "rss_feeds": [
                "https://www.terra.com.br/rss/"
            ]
        },
        {
            "name": "Folha de S.Paulo",
            "base_url": "https://www.folha.uol.com.br",
            "rss_feeds": [
                "https://www.folha.uol.com.br/feed.xml"
            ]
        },
        {
            "name": "R7 - Portal de Notícias",
            "base_url": "https://www.r7.com",
            "rss_feeds": [
                "https://www.r7.com/feed/rss/"
            ]
        },
        {
            "name": "Estadão",
            "base_url": "https://www.estadao.com.br",
            "rss_feeds": [
                "https://www.estadao.com.br/feed/rss/"
            ]
        },
        {
            "name": "Correio Braziliense",
            "base_url": "https://www.correiobraziliense.com.br",
            "rss_feeds": [
                "https://www.correiobraziliense.com.br/rss/"
            ]
        },
        {
            "name": "O Globo",
            "base_url": "https://oglobo.globo.com",
            "rss_feeds": [
                "https://oglobo.globo.com/rss/feed/"
            ]
        },
        {
            "name": "Gazeta do Povo",
            "base_url": "https://www.gazetadopovo.com.br",
            "rss_feeds": [
                "https://www.gazetadopovo.com.br/feed/rss/"
            ]
        },
        {
            "name": "CNN Brasil",
            "base_url": "https://www.cnnbrasil.com.br",
            "rss_feeds": [
                "https://www.cnnbrasil.com.br/feed/"
            ]
        },
        {
            "name": "Metrópoles",
            "base_url": "https://www.metropoles.com",
            "rss_feeds": [
                "https://www.metropoles.com.br/feed/"
            ]
        },
        {
            "name": "Brazilian Report",
            "base_url": "https://brazilian.report",
            "rss_feeds": [
                "https://brazilian.report/feed/"
            ]
        }
    ]
    
    def __init__(self):
        self.aggregator = NewsAggregatorRPA()
    
    def collect_all_portals(self, keywords: List[str] = None) -> Dict[str, Any]:
        """Coleta de todos os portais configurados."""
        return self.aggregator.collect_national(terms=keywords or self.aggregator.BASE_KEYWORDS)
    
    def search(self, query: str, max_pages: int = 3) -> Dict[str, Any]:
        """Busca em todos os portais."""
        return self.aggregator.search(query, max_pages=max_pages)
