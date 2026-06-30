import sys, os, json, re, random, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ["DATABASE_URL"] = "postgresql://postgres:enPySnMfUmDuDViOVUWlxJqrhsmMVWxn@acela.proxy.rlwy.net:38705/railway?sslmode=require"

from app.db.session import SessionLocal
from app.models.search import Search, News
from app.models.lawsuit import Lawsuit
from app.utils.enricher import clean_text

def extract_cnj(text):
    m = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", text)
    if m:
        return m.group(0)
    return None

def extract_tribunal(text):
    tribunals = {
        "TJSP": "SP", "TJRJ": "RJ", "TJMG": "MG", "TJRS": "RS",
        "TJPR": "PR", "TJBA": "BA", "TJDF": "DF", "TJPE": "PE",
        "TJCE": "CE", "TJMT": "MT", "TJGO": "GO", "TJMA": "MA",
        "TJPA": "PA", "TJSC": "SC", "TJES": "ES", "TJRN": "RN",
        "TJPB": "PB", "TJPI": "PI", "TJAL": "AL", "TJSE": "SE",
        "TJRO": "RO", "TJAC": "AC", "TJAM": "AM", "TJRR": "RR",
        "TJTO": "TO", "TJAP": "AP"
    }
    for sigla, uf in tribunals.items():
        if sigla in text.upper():
            return sigla, uf
    return None, None

print("Conectando ao banco Railway...")
db = SessionLocal()

search_record = Search(query="CASOS_REAIS_TRIBUNAIS", tribunal="JusBrasil")
db.add(search_record)
db.commit()
db.refresh(search_record)

termos = [
    "estupro de vulnerável", "abuso sexual", "crime sexual",
    "exploração sexual", "pedofilia", "estupro"
]

import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml"
}

lawsuits_added = 0
news_added = 0
seen_cnjs = set(c for c, in db.query(Lawsuit.cnj).all() if c)
seen_urls = set(u for u, in db.query(News.url).all() if u)

for termo in termos[:5]:
    print("\n=== Buscando: %s ===" % termo)
    query = termo.replace(" ", "+")
    url = "https://www.jusbrasil.com.br/jurisprudencia/busca?q=%s" % query

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        print("Status:", resp.status_code)
        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select(".BaseStyles__Card-sc-1rb3k2v-0") or soup.select("[class*='ResultItem']") or soup.select("article")

        print("Resultados encontrados:", len(results))
        for result in results[:10]:
            title_el = result.select_one("h2, h3, [class*='Title'], [class*='title']")
            snippet_el = result.select_one("p, [class*='Snippet'], [class*='snippet'], [class*='Text']")
            link_el = result.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            link = link_el["href"] if link_el and link_el.has_attr("href") else ""

            if not title:
                continue
            if link and link in seen_urls:
                continue

            cnj = extract_cnj(snippet or title)
            tribunal_sigla, uf = extract_tribunal(snippet or title)

            cnj_valid = cnj and re.sub(r"\D", "", cnj) not in seen_cnjs

            try:
                news_item = News(
                    search_id=search_record.id,
                    title=clean_text(title)[:200],
                    url=link or url,
                    source="JusBrasil",
                    snippet=clean_text(snippet)[:500],
                    state=uf,
                )
                db.add(news_item)
                seen_urls.add(link)
                news_added += 1
                print("  + Noticia: %s" % title[:60])
            except Exception:
                pass

            if cnj_valid and lawsuits_added < 30:
                parties = {}
                if snippet:
                    names = re.findall(r"([A-Z][A-Z\s]{4,})", snippet.upper())
                    passivo = [{"nome": n.strip().title(), "tipo": "Réu"} for n in names[:2] if len(n.strip().split()) >= 2]
                    if passivo:
                        parties = {"Polo Ativo": [{"nome": "Ministério Público", "tipo": "Autor"}], "Polo Passivo": passivo}

                try:
                    lawsuit = Lawsuit(
                        cnj=re.sub(r"\D", "", cnj),
                        tribunal=tribunal_sigla or uf or "BR",
                        state=uf or "BR",
                        subject="Crimes Sexuais",
                        parties=json.dumps(parties or {"Polo Ativo": [{"nome": "Ministério Público", "tipo": "Autor"}]}, ensure_ascii=False),
                    )
                    db.add(lawsuit)
                    seen_cnjs.add(re.sub(r"\D", "", cnj))
                    lawsuits_added += 1
                    print("  + Processo: %s" % cnj)
                except Exception:
                    pass

        time.sleep(2)

    except Exception as e:
        print("  Erro: %s" % e)

db.commit()
db.close()
print("\nConcluido! Noticias=%d Processos=%d" % (news_added, lawsuits_added))
