#!/usr/bin/env python3
"""
Script de Testes - Get Shit Done
Testa cada componente do sistema fragmentado
"""
import sys
import os
import time

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv()

def test_step(name, func):
    """Executa um teste e reporta o resultado"""
    print(f"\n{'='*60}")
    print(f"TESTE: {name}")
    print('='*60)
    try:
        result = func()
        print(f"[OK] SUCESSO: {result}")
        return True
    except Exception as e:
        print(f"[X] FALHA: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================
# ETAPA 1: Banco de Dados e Modelos
# ============================================================

def test_database_connection():
    from app.db.session import engine, SessionLocal
    from app.models.search import Search, SearchResult, News
    from app.models.lawsuit import Lawsuit
    from app.db.base import Base
    
    # Testa conexão
    conn = engine.connect()
    conn.close()
    
    # Testa criação de tabelas
    Base.metadata.create_all(bind=engine)
    
    # Testa sessão
    db = SessionLocal()
    count = db.query(News).count()
    db.close()
    
    return f"Banco OK - {count} notícias cadastradas"

def test_models():
    from app.db.session import SessionLocal
    from app.models.search import Search, News
    
    db = SessionLocal()
    
    # Testa inserir uma notícia de teste
    test_news = News(
        title="TESTE: Notícia de Teste",
        url="https://teste.com.br/noticia-teste",
        source="Teste",
        snippet="Esta é uma notícia de teste",
        state="SP",
        city="São Paulo"
    )
    db.add(test_news)
    db.commit()
    
    # Busca
    result = db.query(News).filter(News.title.like("%TESTE%")).first()
    assert result is not None, "Não encontrou notícia de teste"
    
    # Remove
    db.delete(result)
    db.commit()
    db.close()
    
    return "Modelos funcionando"

# ============================================================
# ETAPA 2: APIs e Endpoints
# ============================================================

def test_api_imports():
    from app.api.endpoints import search, stats
    return "Endpoints importados com sucesso"

def test_search_endpoint_logic():
    from app.api.endpoints.search import (
        is_relevant_content, 
        normalize_url, 
        normalize_text,
        RELEVANT_KEYWORDS
    )
    
    # Testa normalização de URL
    url = normalize_url("https://g1.globo.com/?utm_source=google.com")
    assert "utm_" not in url, "URL não foi normalizada"
    
    # Testa relevância
    assert is_relevant_content("estupro de vulnerável"), "Não detectou relevância"
    assert is_relevant_content("exploração sexual infantil"), "Não detectou relevância"
    
    return "Lógica de busca OK"

def test_stats_endpoint_logic():
    from app.api.endpoints.stats import (
        normalize_text,
        is_relevant_content,
        parse_terms
    )
    
    # Testa parse de termos
    terms = parse_terms("termo1,termo2|termo3")
    assert len(terms) == 3, "Parse de termos falhou"
    
    # Testa relevância
    assert is_relevant_content("crime sexual"), "Não detectou crime sexual"
    
    return "Lógica de stats OK"

def test_catalog_api():
    from app.db.session import SessionLocal
    from app.models.search import News
    from sqlalchemy import func
    
    db = SessionLocal()
    
    # Conta notícias por estado
    results = db.query(
        News.state, 
        func.count(News.id).label('total')
    ).group_by(News.state).all()
    
    print(f"  Notícias por estado: {len(results)} estados")
    for r in results[:5]:
        print(f"    {r.state}: {r.total}")
    
    db.close()
    return "API de catálogo OK"

# ============================================================
# ETAPA 3: RPA de Notícias
# ============================================================

def test_rpa_google_news():
    from app.rpa.google_news import GoogleNewsRPA
    
    rpa = GoogleNewsRPA()
    result = rpa.search("estupro", max_pages=1)
    
    assert result.get("status") == "success", "RPA falhou"
    assert len(result.get("results", [])) > 0, "Nenhum resultado"
    
    print(f"  Coletou {len(result.get('results', []))} notícias")
    
    return "Google News RPA OK"

def test_rpa_news_aggregator():
    from app.rpa.news_aggregator import NewsAggregatorRPA
    
    rpa = NewsAggregatorRPA()
    result = rpa.search("abuso sexual", max_pages=1)
    
    assert result.get("status") == "success", "Agregador falhou"
    assert len(result.get("results", [])) > 0, "Nenhum resultado"
    
    print(f"  Coletou {len(result.get('results', []))} notícias do agregador")
    
    return "News Aggregator RPA OK"

def test_rss_feeds():
    from app.rpa.news_aggregator import NewsAggregatorRPA
    
    rpa = NewsAggregatorRPA()
    
    # Testa RSS da Folha
    items = rpa._fetch_rss("https://www.folha.uol.com.br/feed.xml", "Folha", max_items=5)
    
    print(f"  RSS Folha: {len(items)} notícias")
    
    return "RSS feeds OK"

# ============================================================
# ETAPA 4: Frontend
# ============================================================

def test_frontend_static_files():
    import os
    
    files = [
        "static/index.html",
        "static/vendor/leaflet/leaflet.js",
        "static/vendor/leaflet/leaflet.css",
    ]
    
    for f in files:
        path = os.path.join(os.getcwd(), f)
        assert os.path.exists(path), f"Arquivo não encontrado: {f}"
    
    return "Arquivos estáticos OK"

def test_frontend_html_structure():
    with open("static/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Verifica estruturas essenciais
    assert "<html" in content.lower(), "HTML tag faltando"
    assert "<body>" in content.lower(), "BODY tag faltando"
    assert "catalog-grid" in content, "Grid de catálogo faltando"
    assert "modal" in content.lower(), "Modal faltando"
    assert "map" in content.lower(), "Mapa faltando"
    
    return "Estrutura HTML OK"

def test_constants():
    from app.core.constants import (
        RELEVANT_KEYWORDS,
        STATE_COORDS,
        COORDS,
        TRIBUNAL_TO_STATE
    )
    
    assert len(RELEVANT_KEYWORDS) > 0, "Keywords vazias"
    assert len(STATE_COORDS) > 0, "Estados vazios"
    assert len(COORDS) > 0, "Coordenadas vazias"
    assert "SP" in STATE_COORDS, "SP não encontrada"
    assert "TJSP" in TRIBUNAL_TO_STATE, "TJSP não encontrado"
    
    return f"Constants OK ({len(RELEVANT_KEYWORDS)} keywords, {len(STATE_COORDS)} estados)"

# ============================================================
# EXECUÇÃO DOS TESTES
# ============================================================

def main():
    print("""
    ===========================================================
           TESTE DO SISTEMA - GET SHIT DONE
           JuriPopular / Reveal
    ===========================================================
    """)
    
    results = []
    
    # Etapa 1: Banco
    print("\n\n### ETAPA 1: BANCO DE DADOS ###")
    results.append(("DB Connection", test_step("DB Connection", test_database_connection)))
    results.append(("Models", test_step("Models", test_models)))
    results.append(("Constants", test_step("Constants", test_constants)))
    
    # Etapa 2: APIs
    print("\n\n### ETAPA 2: APIs E ENDPOINTS ###")
    results.append(("API Imports", test_step("API Imports", test_api_imports)))
    results.append(("Search Logic", test_step("Search Logic", test_search_endpoint_logic)))
    results.append(("Stats Logic", test_step("Stats Logic", test_stats_endpoint_logic)))
    results.append(("Catalog API", test_step("Catalog API", test_catalog_api)))
    
    # Etapa 3: RPA
    print("\n\n### ETAPA 3: RPA DE NOTÍCIAS ###")
    results.append(("Google News RPA", test_step("Google News RPA", test_rpa_google_news)))
    results.append(("News Aggregator", test_step("News Aggregator", test_rpa_news_aggregator)))
    results.append(("RSS Feeds", test_step("RSS Feeds", test_rss_feeds)))
    
    # Etapa 4: Frontend
    print("\n\n### ETAPA 4: FRONTEND ###")
    results.append(("Static Files", test_step("Static Files", test_frontend_static_files)))
    results.append(("HTML Structure", test_step("HTML Structure", test_frontend_html_structure)))
    
    # Resumo
    print("\n\n" + "="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[PASSOU]" if result else "[FALHOU]"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\nTODOS OS TESTES PASSARAM!")
        return 0
    else:
        print(f"\nATENCAO: {total - passed} teste(s) falharam!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
