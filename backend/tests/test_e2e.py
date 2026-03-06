import pytest
from playwright.sync_api import Page, expect
import re
import time

# Configuration
BASE_URL = "http://localhost:8001"

@pytest.fixture(scope="function", autouse=True)
def before_each(page: Page):
    """Ensure the app is reachable and starts in a clean state (catalog closed)."""
    try:
        page.goto(BASE_URL, timeout=5000)
        # The catalog opens automatically on load. We close it to ensure a clean state for map tests.
        # We wait a bit for the animation/JS to settle
        page.wait_for_timeout(500)
        if page.locator("#catalog-view").is_visible():
            page.keyboard.press("Escape")
            expect(page.locator("#catalog-view")).not_to_be_visible()
    except Exception as e:
        pytest.fail(f"Could not reach {BASE_URL}. Is the backend running? Error: {e}")

def test_homepage_loads(page: Page):
    """Verify basic homepage structure and title."""
    expect(page).to_have_title("JuriPopular | Expondo o que a justiça esconde")
    expect(page.locator("h1")).to_contain_text("JuriPopular")
    expect(page.locator("#map")).to_be_visible()
    expect(page.locator("button", has_text="CATÁLOGO DE NOTÍCIAS")).to_be_visible()

def test_catalog_opens_and_closes(page: Page):
    """Verify catalog modal interaction."""
    page.click("button:has-text('CATÁLOGO DE NOTÍCIAS')")
    expect(page.locator("#catalog-view")).to_be_visible()
    expect(page.locator("#catalog-view h2")).to_contain_text("CATÁLOGO DE INTELIGÊNCIA")
    
    page.keyboard.press("Escape")
    expect(page.locator("#catalog-view")).not_to_be_visible()

def test_filter_judicial(page: Page):
    """Testa se o filtro 'Judicial' remove notícias da grade"""
    page.click("button[onclick='openCatalog()']")
    page.wait_for_selector("#catalog-grid")
    
    # Intercepta a requisição para garantir que o parâmetro está indo
    with page.expect_response(lambda response: "source_type=judicial" in response.url and response.status == 200) as response_info:
        page.select_option("#filter-type", "judicial")
    
    # Aguarda a atualização da grade (pode levar um tempo para limpar e renderizar)
    page.wait_for_timeout(1000) 
    
    # Verifica se NÃO existem cards de notícias
    # Cards de notícias têm ícone 📰 ou imagem, cards judiciais têm ícone ⚖️
    
    # Opção 1: Verificar texto dos botões ou ícones
    # Notícias geralmente não têm o ícone de balança
    
    # Vamos contar quantos itens existem
    items = page.locator("#catalog-grid > div")
    count = items.count()
    print(f"Items found: {count}")
    
    if count > 0:
        # Verifica se todos são judiciais (contêm ícone de balança ou classe específica)
        # No HTML: isJudicial ? 'bg-blue-900/10 ...' : 'bg-white/5 ...'
        # Judicial tem borda azulada (border-blue-500/30)
        
        judicial_cards = page.locator("#catalog-grid > div.bg-blue-900\\/10")
        news_cards = page.locator("#catalog-grid > div.bg-white\\/5")
        
        expect(judicial_cards).to_have_count(count)
        expect(news_cards).to_have_count(0)

def test_filter_news(page: Page):
    """Testa se o filtro 'Notícias' remove processos da grade"""
    page.click("button[onclick='openCatalog()']")
    page.wait_for_selector("#catalog-grid")
    
    with page.expect_response(lambda response: "source_type=news" in response.url and response.status == 200) as response_info:
        page.select_option("#filter-type", "news")
        
    page.wait_for_timeout(1000)
    
    items = page.locator("#catalog-grid > div")
    count = items.count()
    
    if count > 0:
        judicial_cards = page.locator("#catalog-grid > div.bg-blue-900\\/10")
        news_cards = page.locator("#catalog-grid > div.bg-white\\/5")
        
        expect(news_cards).to_have_count(count)
        expect(judicial_cards).to_have_count(0)

def test_map_filter_toggle(page: Page):
    """Verify map layer toggles."""
    # Ensure catalog is closed (handled by before_each)
    expect(page.locator("#catalog-view")).not_to_be_visible()
    
    news_checkbox = page.locator("#layer-news")
    expect(news_checkbox).to_be_checked()
    
    # Toggle News off
    news_checkbox.uncheck()
    # Check visual feedback (opacity class added)
    news_label = page.locator("label", has_text="MÍDIA / NOTÍCIAS").locator("span")
    expect(news_label).to_have_class(re.compile(r"opacity-40"))
    expect(news_label).to_have_class(re.compile(r"line-through"))
    
    # Toggle News on
    news_checkbox.check()
    expect(news_label).not_to_have_class(re.compile(r"opacity-40"))

def test_details_modal(page: Page):
    """Verify opening details of an item."""
    page.click("button:has-text('CATÁLOGO DE NOTÍCIAS')")
    # Wait for grid to populate
    page.wait_for_timeout(2000)
    
    items = page.locator("#catalog-grid > div")
    if items.count() > 0:
        # Click the first item
        items.first.click()
        # Verify modal opens (ID is modal-overlay based on index.html analysis)
        expect(page.locator("#modal-overlay")).to_be_visible()
        
        # Close details
        page.click("#modal-close")
        expect(page.locator("#modal-overlay")).not_to_be_visible()
    else:
        pytest.skip("No items in catalog to test details")

def test_mobile_responsiveness(page: Page):
    """Verify layout on mobile viewport."""
    page.set_viewport_size({"width": 375, "height": 667})
    page.reload()
    page.wait_for_timeout(500)
    
    # Close catalog if auto-opened
    if page.locator("#catalog-view").is_visible():
        page.keyboard.press("Escape")
    
    # Verify map is visible
    expect(page.locator("#map")).to_be_visible()
    
    # Verify Catalog button is visible
    expect(page.locator("button", has_text="CATÁLOGO")).to_be_visible()
